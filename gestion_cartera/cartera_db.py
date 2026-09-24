"""Consultas de base de datos para la página CARTERA (tenencias calculadas
a partir del histórico de operaciones) y para la página BROKERS (alta de
brokers y control de existencias por bróker, agregando las dos carteras).

A partir de ahora el bróker se ignora en todos los cálculos de tenencias
de CARTERA/VALOR (se agregan Compra/Venta/Script de todos los brokers de
la cartera); el bróker solo se sigue usando para: registrar cada operación
(sigue siendo obligatorio en el alta) y para las validaciones de SALDO al
dar de alta o editar una Venta/Dividendo/Prima (porque solo puedes vender
lo que tienes depositado en ESE bróker en concreto, ver
operaciones_db.calcular_saldo). Para el control de existencias por bróker
(página BROKERS), en cambio, se agregan las dos carteras a la vez, porque
un extracto real del bróker no sabe nada de esa distinción interna.
"""

import math
from datetime import date

import reflex as rx
import sqlmodel

from gestion_cartera.format_utils import formatear_eur, formatear_pct, formatear_titulos
from gestion_cartera.models import Broker, Operacion, Sector, Valor
from gestion_cartera.styles import gain_loss_color

# Un Script (tanto si el derecho se compró como si se vendió) siempre
# aporta títulos. Lo que distingue a un Script con derecho VENDIDO
# (Operacion.tipo_derecho_script == "Venta") es que NO aporta coste de
# compra: los títulos recibidos entran con coste 0 (el importe recibido
# por la venta del derecho computa aparte, como un dividendo, no como
# coste de las acciones).
#
# Para que el orden de los lotes FIFO (ver PosicionFIFO más abajo) sea
# correcto cuando varias operaciones caen el mismo día (típico en una
# operación corporativa: consolidación/contrasplit, donde se venden las
# acciones viejas y se compran las nuevas el mismo día), las operaciones
# se procesan en orden cronológico y, dentro del mismo día, primero
# Dividendo/Prima (afectan a la posición tal y como estaba antes de la
# operación corporativa), luego Venta (consume los lotes más antiguos
# que ya hubiera) y por último Compra/Script (añaden lotes nuevos, que
# por tanto NO se venden a sí mismos ese mismo día). Split/Contrasplit
# se procesan justo antes que Venta: son la propia "operación
# corporativa" que reescala lo que ya había, así que tiene que
# aplicarse ANTES de que una Venta del mismo día consuma lotes (que
# deben quedar ya reescalados) pero DESPUÉS de Dividendo/Prima (que se
# calculan sobre la posición tal y como estaba antes de la operación
# corporativa).
_PRIORIDAD_MISMO_DIA = {
    "Dividendo": 0,
    "Prima": 0,
    "Split": 1,
    "Contrasplit": 1,
    "Venta": 2,
    "Compra": 3,
    "Script": 3,
}


class _LoteFIFO:
    """Un lote de compra vivo: cuántos títulos quedan de él y a qué
    coste unitario se compraron (puede cambiar por una Prima, ver
    `PosicionFIFO.aplicar_prima`)."""

    __slots__ = ("titulos", "coste_unitario")

    def __init__(self, titulos: float, coste_unitario: float):
        self.titulos = titulos
        self.coste_unitario = coste_unitario


class PosicionFIFO:
    """Valoración de una posición por FIFO ("first in, first out"): cada
    Compra (o Script con derecho comprado) añade un LOTE nuevo al final
    de la cola; cada Venta consume títulos de los lotes más antiguos
    primero -- los primeros títulos que se compraron son los primeros
    que se venden, tal cual pidió Gabriel, en vez del coste medio
    ponderado que se usaba antes (que valoraba cualquier venta al mismo
    precio medio de toda la posición, sin importar el orden de compra).

    Cuando la posición llega a 0 títulos la cola de lotes queda
    simplemente vacía: una Compra posterior añade un lote nuevo sin más,
    así que a diferencia del coste medio ponderado no hace falta ningún
    "reinicio" explícito del acumulador."""

    def __init__(self):
        self._lotes: list[_LoteFIFO] = []

    @property
    def titulos(self) -> float:
        return sum(l.titulos for l in self._lotes)

    @property
    def coste_total(self) -> float:
        """Coste de compra de TODOS los títulos que quedan (la suma de
        lo que costó cada lote vivo), equivalente al antiguo
        'coste_compra' pero calculado lote a lote."""
        return sum(l.titulos * l.coste_unitario for l in self._lotes)

    def comprar(self, num_titulos: float, coste_unitario: float) -> None:
        if num_titulos <= 0:
            return
        self._lotes.append(_LoteFIFO(num_titulos, coste_unitario))

    def vender(self, num_titulos: float) -> float:
        """Consume `num_titulos` de los lotes más antiguos (FIFO) y
        devuelve el COSTE de esos títulos vendidos -- la plusvalía
        realizada de esta venta en concreto es `importe_venta - esto`."""
        restante = num_titulos
        coste_vendido = 0.0
        while restante > 1e-9 and self._lotes:
            lote = self._lotes[0]
            consumido = min(lote.titulos, restante)
            coste_vendido += consumido * lote.coste_unitario
            lote.titulos -= consumido
            restante -= consumido
            if lote.titulos <= 1e-9:
                self._lotes.pop(0)
        # Si `restante` > 0 aquí es que se está vendiendo más de lo que
        # hay en los lotes -- no debería pasar gracias a la validación
        # de saldo (ver operaciones_db.validar_saldo_nunca_negativo),
        # pero por seguridad no se lanza excepción: esos títulos de más
        # sencillamente no aportan coste conocido.
        return coste_vendido

    def aplicar_prima(self, importe: float) -> None:
        """Una Prima no aporta ni resta títulos, pero SÍ reduce el coste
        de las acciones que ya se poseen (como una devolución parcial de
        lo pagado por ellas): se reparte el importe a partes iguales por
        título entre TODOS los lotes vivos, igual efecto neto que restar
        del acumulador de coste medio ponderado de antes, pero ahora
        aplicado lote a lote para no perder el desglose FIFO."""
        titulos_totales = self.titulos
        if titulos_totales <= 1e-9:
            return
        reduccion_por_titulo = importe / titulos_totales
        for lote in self._lotes:
            lote.coste_unitario -= reduccion_por_titulo

    def aplicar_split(self, ratio: float) -> None:
        """Split o contrasplit (`ratio` = nuevo/antiguo, p.ej. 10.0 en
        un split 1→10, o 0.1 en un contrasplit 10→1): reescala TODOS
        los lotes vivos multiplicando sus títulos y dividiendo su coste
        unitario por el mismo factor, así que el coste TOTAL de cada
        lote no cambia ni un céntimo -- solo cómo se reparte entre más
        (split) o menos (contrasplit) títulos. A diferencia de
        `comprar`, no añade ningún lote nuevo: conserva intactos el
        desglose FIFO y la fecha de compra de cada lote existente. Para
        la fracción de título que un ratio no exacto pueda dejar
        sobrando, ver `aplicar_split_y_fraccion` (fuera de esta
        clase)."""
        if not ratio or ratio <= 0:
            return
        for lote in self._lotes:
            lote.titulos *= ratio
            lote.coste_unitario /= ratio

# YOC (yield on cost) del año anterior: igual que la rentabilidad por
# dividendo (R.D.), pero usando como referencia el valor de compra que
# se tenía a 31 de diciembre de ese año (no la posición actual, que
# puede haber cambiado desde entonces) en vez de la cotización actual --
# así se ve el retorno real sobre lo que se pagó, no sobre lo que vale
# hoy. Los "dividendos" del año, a su vez, incluyen también lo cobrado
# por vender derechos (Script con derecho VENDIDO), no solo el
# Dividendo en sentido estricto.

# Tolerancia para comparaciones de nº de títulos con coma flotante (ya
# usada en PosicionFIFO.vender) -- reutilizada aquí para decidir si un
# Split/Contrasplit deja un número entero de títulos o si sobra/falta
# una fracción.
EPSILON_TITULOS = 1e-6


def aplicar_split_y_fraccion(
    posicion: "PosicionFIFO", op: "Operacion"
) -> tuple[float, float]:
    """Aplica un Split o Contrasplit (`op.ratio`) a `posicion`: reescala
    TODOS los lotes vivos (ver `PosicionFIFO.aplicar_split`) y, si el
    resultado no es un número entero de títulos, resuelve la fracción
    sobrante según `op.tipo_ajuste_fraccion` -- ver el comentario de ese
    campo en models.py y la conversación de diseño del 24/09/2026
    (Split/Contrasplit, fracciones, cash-in-lieu):

    - "Venta": el bróker pagó esa fracción -- se vende del FIFO
      (mismo mecanismo que una Venta normal) y se devuelve su coste,
      para que quien llama pueda calcular la plusvalía de esa fracción
      si le interesa (ver resumen_irpf_db.py).
    - "Compra": hubo que abonar algo para completarla -- se compra al
      FIFO con ese coste.
    - None (ajuste "gratis" o resultado ya entero): no hace falta nada
      más, la fracción (si la hay) se pierde o se gana sin coste.

    Devuelve (fraccion, coste_o_0): `fraccion` es el nº de títulos de
    la fracción tratada (0.0 si el resultado ya era entero), y
    `coste_o_0` el coste FIFO de esa fracción SOLO cuando
    tipo_ajuste_fraccion == "Venta" (para la plusvalía); en cualquier
    otro caso es 0.0."""
    posicion.aplicar_split(op.ratio)

    if op.tipo_ajuste_fraccion == "Venta":
        entero_abajo = math.floor(posicion.titulos + EPSILON_TITULOS)
        fraccion = posicion.titulos - entero_abajo
        if fraccion > EPSILON_TITULOS:
            coste = posicion.vender(fraccion)
            return fraccion, coste
    elif op.tipo_ajuste_fraccion == "Compra":
        entero_arriba = math.ceil(posicion.titulos - EPSILON_TITULOS)
        fraccion = entero_arriba - posicion.titulos
        if fraccion > EPSILON_TITULOS:
            coste_unitario = (op.importe / fraccion) if op.importe else 0.0
            posicion.comprar(fraccion, coste_unitario)
            return fraccion, 0.0
    return 0.0, 0.0


def _anio_anterior() -> int:
    return date.today().year - 1


def _aporta_titulos(op: Operacion) -> bool:
    return op.tipo_operacion in ("Compra", "Script")


def _aporta_coste(op: Operacion) -> bool:
    if op.tipo_operacion == "Compra":
        return True
    if op.tipo_operacion == "Script":
        return op.tipo_derecho_script == "Compra"
    return False


# --- Rentabilidad de la cartera (TIR / XIRR) ---------------------------
#
# Rentabilidad anual money-weighted (tiene en cuenta CUÁNDO se hizo cada
# desembolso, no solo cuánto). Cada operación aporta su movimiento de
# caja real en su fecha, nunca un "resultado" ya calculado (el resultado
# de una Venta concreta no se mete aparte: ya queda reflejado solo por
# tener su importe de entrada y el de la Compra de salida, cada uno en
# su fecha -- meterlo aparte sería contar la plusvalía dos veces):
#   Compra, Script con derecho de compra -> sale dinero (flujo negativo)
#   Venta, Prima                         -> entra dinero (flujo positivo)
#   Dividendo, Script con derecho vendido -> entra dinero (flujo positivo)
# Siempre en BRUTO, sin descontar retenciones: las retenciones solo se
# anotan de cara a la declaración de la renta, no representan dinero que
# de verdad falte en ningún cálculo de rentabilidad ni de coste.
# Se calculan dos TIR distintas añadiendo un último flujo positivo a
# fecha de hoy con el valor de las tenencias actuales:
#   - con revalorización: usando el valor de mercado actual (refleja
#     también la subida o bajada de cotización).
#   - sin revalorización: usando el valor de compra actual en su lugar
#     (como si no hubiera habido ni ganancia ni pérdida de cotización;
#     aísla el efecto puro de los dividendos y el momento de cada pago).
def _flujo_caja_operacion(op: Operacion) -> float:
    """Movimiento de caja BRUTO de una operación (positivo = entra
    dinero, negativo = sale dinero). 0.0 para tipos sin efecto en caja."""
    tipo = op.tipo_operacion
    if tipo == "Compra":
        return -op.importe
    if tipo in ("Venta", "Prima", "Dividendo"):
        return op.importe
    if tipo == "Script":
        return -op.importe if op.tipo_derecho_script == "Compra" else op.importe
    return 0.0


def _xirr(flujos: list[tuple[date, float]]) -> float | None:
    """TIR anual (tasa r tal que la suma de flujo/(1+r)^(días/365) es 0),
    resuelta por bisección sobre un rango amplio (-99.9999% a +1000%
    anual). Devuelve None si no hay datos suficientes o si el NPV no
    cambia de signo en ese rango (no se puede acotar una solución)."""
    if len(flujos) < 2:
        return None
    fecha0 = min(f for f, _ in flujos)

    def npv(tasa: float) -> float:
        total = 0.0
        for fecha, importe in flujos:
            dias = (fecha - fecha0).days
            total += importe / (1 + tasa) ** (dias / 365.0)
        return total

    lo, hi = -0.999999, 10.0
    npv_lo, npv_hi = npv(lo), npv(hi)
    if npv_lo == 0:
        return lo
    if npv_hi == 0:
        return hi
    if (npv_lo > 0) == (npv_hi > 0):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        npv_mid = npv(mid)
        if abs(npv_mid) < 1e-6:
            return mid
        if (npv_mid > 0) == (npv_lo > 0):
            lo, npv_lo = mid, npv_mid
        else:
            hi, npv_hi = mid, npv_mid
    return (lo + hi) / 2


def calcular_tir(id_cartera: int) -> dict:
    """{"con_revalorizacion": float|None, "sin_revalorizacion": float|None}
    (en % anual). Usa el histórico COMPLETO de operaciones de la cartera
    (también las de valores ya vendidos del todo), más un último flujo a
    fecha de hoy con el valor de las tenencias actuales."""
    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_cartera == id_cartera)
        ).all()

    flujos = [
        (op.fecha, importe)
        for op in operaciones
        if (importe := _flujo_caja_operacion(op)) != 0.0
    ]
    if not flujos:
        return {"con_revalorizacion": None, "sin_revalorizacion": None}

    tenencias = obtener_tenencias(id_cartera)
    valor_mercado_total = sum(f["valor_mercado"] for f in tenencias)
    valor_compra_total = sum(f["valor_compra"] for f in tenencias)
    hoy = date.today()

    tir_con = _xirr(flujos + [(hoy, valor_mercado_total)])
    tir_sin = _xirr(flujos + [(hoy, valor_compra_total)])
    return {
        "con_revalorizacion": round(tir_con * 100, 2) if tir_con is not None else None,
        "sin_revalorizacion": round(tir_sin * 100, 2) if tir_sin is not None else None,
    }


def obtener_tenencias(id_cartera: int) -> list[dict]:
    """Una fila por valor con saldo > 0 en esta cartera (todos los
    brokers agregados): nº de títulos, precio medio de compra (coste de
    los lotes que TODAVÍA se poseen, valorados por FIFO -- ver
    `PosicionFIFO`), y los datos de cotización ya guardados en el Valor
    (los refresca aparte `refrescar_cotizaciones`, antes de llamar a
    esta función, para que salgan actualizados)."""
    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_cartera == id_cartera)
        ).all()
        operaciones = sorted(
            operaciones,
            key=lambda op: (op.fecha, _PRIORIDAD_MISMO_DIA.get(op.tipo_operacion, 1)),
        )

        anio_anterior = _anio_anterior()
        fecha_cierre = date(anio_anterior, 12, 31)

        por_valor: dict[int, dict] = {}
        for op in operaciones:
            acc = por_valor.setdefault(
                op.id_valor,
                {
                    "posicion": PosicionFIFO(),
                    "dividendos_anio_anterior": 0.0,
                    "valor_compra_cierre": None,
                },
            )
            posicion: PosicionFIFO = acc["posicion"]

            # El YOC del año anterior se calcula sobre la "foto" de la
            # cartera a 31 de diciembre de ese año (coste de los títulos
            # que se tenían entonces), no sobre la posición actual: se
            # toma justo antes de procesar la primera operación
            # posterior a esa fecha.
            if acc["valor_compra_cierre"] is None and op.fecha > fecha_cierre:
                acc["valor_compra_cierre"] = posicion.coste_total if posicion.titulos > 0 else 0.0

            # Efecto de la operación sobre la posición (títulos/coste).
            if op.tipo_operacion == "Venta":
                posicion.vender(op.num_titulos)
            elif op.tipo_operacion == "Prima":
                posicion.aplicar_prima(op.importe)
            elif op.tipo_operacion in ("Split", "Contrasplit"):
                aplicar_split_y_fraccion(posicion, op)
            elif _aporta_titulos(op):
                coste_unitario = (
                    (op.importe / op.num_titulos)
                    if _aporta_coste(op) and op.num_titulos
                    else 0.0
                )
                posicion.comprar(op.num_titulos, coste_unitario)

            # "Dividendos" del año anterior (independiente de lo de
            # arriba): Dividendo normal, o Script con derecho VENDIDO,
            # cuyo importe cobrado computa también como un dividendo.
            if op.fecha.year == anio_anterior:
                if op.tipo_operacion == "Dividendo":
                    acc["dividendos_anio_anterior"] += op.importe
                elif op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta":
                    acc["dividendos_anio_anterior"] += op.importe

        # Valores cuyo histórico entero cae dentro (o antes de) el año de
        # cierre -- sin ninguna operación posterior que dispare la "foto"
        # de arriba -- se resuelven aquí con el estado final del bucle.
        for acc in por_valor.values():
            if acc["valor_compra_cierre"] is None:
                posicion: PosicionFIFO = acc["posicion"]
                acc["valor_compra_cierre"] = posicion.coste_total if posicion.titulos > 0 else 0.0

        filas = []
        valor_total_cartera = 0.0
        pendientes = []
        for id_valor, acc in por_valor.items():
            posicion: PosicionFIFO = acc["posicion"]
            titulos = posicion.titulos
            if titulos <= 0:
                continue
            valor = session.get(Valor, id_valor)
            if valor is None:
                continue
            sector = session.get(Sector, valor.id_sector)

            valor_compra = posicion.coste_total
            precio_medio = valor_compra / titulos if titulos else 0.0
            cotizacion = valor.cotizacion_eur or 0.0
            valor_mercado = cotizacion * titulos
            plusvalia_eur = valor_mercado - valor_compra
            plusvalia_pct = (plusvalia_eur / valor_compra * 100) if valor_compra else 0.0
            valor_total_cartera += valor_mercado

            valor_compra_cierre = acc["valor_compra_cierre"] or 0.0
            yoc_anterior = (
                (acc["dividendos_anio_anterior"] / valor_compra_cierre * 100)
                if valor_compra_cierre
                else 0.0
            )

            pendientes.append(
                {
                    "id_valor": id_valor,
                    "ticker": valor.ticker,
                    "mercado": valor.mercado,
                    "empresa": valor.empresa,
                    "moneda": valor.moneda,
                    "zona": valor.zona,
                    "supersector": sector.supersector if sector else "",
                    "sector": sector.sector if sector else "",
                    "grupo": sector.grupo if sector else "",
                    "num_titulos": titulos,
                    "num_titulos_mostrar": formatear_titulos(titulos),
                    "precio_medio": round(precio_medio, 2),
                    "precio_medio_mostrar": formatear_eur(precio_medio),
                    "cotizacion_actual": round(cotizacion, 2),
                    "cotizacion_actual_mostrar": formatear_eur(cotizacion),
                    "valor_compra": round(valor_compra, 2),
                    "valor_mercado": round(valor_mercado, 2),
                    "valor_mercado_mostrar": formatear_eur(valor_mercado),
                    "plusvalia_eur": round(plusvalia_eur, 2),
                    "plusvalia_eur_mostrar": formatear_eur(plusvalia_eur),
                    "plusvalia_pct": round(plusvalia_pct, 2),
                    "plusvalia_pct_mostrar": formatear_pct(plusvalia_pct),
                    "yoc_anterior": round(yoc_anterior, 2),
                    "yoc_anterior_mostrar": formatear_pct(yoc_anterior),
                    # Color ya resuelto en el backend: comparar campos de un
                    # dict genérico (item["x"] > 0) dentro del componente no
                    # funciona en Reflex porque no conoce el tipo del campo.
                    "color_plusvalia": gain_loss_color(plusvalia_eur),
                    "cotizacion_actualizada_en": (
                        valor.cotizacion_actualizada_en.strftime("%d/%m/%Y %H:%M")
                        if valor.cotizacion_actualizada_en
                        else ""
                    ),
                }
            )

        for fila in pendientes:
            peso = (
                round(fila["valor_mercado"] / valor_total_cartera * 100, 2)
                if valor_total_cartera
                else 0.0
            )
            fila["peso_cartera_pct"] = peso
            fila["peso_cartera_pct_mostrar"] = formatear_pct(peso)
            filas.append(fila)

        return sorted(filas, key=lambda f: f["valor_mercado"], reverse=True)


def obtener_valores_liquidados(id_cartera: int) -> list[dict]:
    """Valores de esta cartera con saldo actual de 0 títulos (posición
    liquidada del todo, aunque en algún momento se hayan tenido) -- para
    que también aparezcan en la página CARTERA y se pueda entrar a ver su
    histórico completo, aunque ya no formen parte de la cartera actual.

    A diferencia de `obtener_tenencias`, aquí no interesa el coste medio
    "vivo" (que se reinicia a 0 en cada liquidación total, ver
    `_PRIORIDAD_MISMO_DIA`), sino cuánto se invirtió en total a lo largo
    de toda la vida del valor en esta cartera, así que se acumula aparte
    sin reiniciar nunca."""
    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_cartera == id_cartera)
        ).all()
        operaciones = sorted(
            operaciones,
            key=lambda op: (op.fecha, _PRIORIDAD_MISMO_DIA.get(op.tipo_operacion, 1)),
        )

        por_valor: dict[int, dict] = {}
        for op in operaciones:
            acc = por_valor.setdefault(
                op.id_valor,
                {
                    "titulos": 0.0,
                    "invertido_historico": 0.0,
                    "dividendos_acumulados": 0.0,
                    "venta_derechos_acumulada": 0.0,
                    "importe_ventas_acumulado": 0.0,
                    "fecha_ultima_operacion": op.fecha,
                },
            )
            acc["fecha_ultima_operacion"] = max(acc["fecha_ultima_operacion"], op.fecha)

            if op.tipo_operacion == "Venta":
                acc["titulos"] -= op.num_titulos
                acc["importe_ventas_acumulado"] += op.importe
            elif _aporta_titulos(op):
                acc["titulos"] += op.num_titulos
                if _aporta_coste(op):
                    acc["invertido_historico"] += op.importe

            if op.tipo_operacion == "Dividendo":
                acc["dividendos_acumulados"] += op.importe
            elif op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta":
                acc["venta_derechos_acumulada"] += op.importe

        filas = []
        for id_valor, acc in por_valor.items():
            if acc["titulos"] > 1e-9 or acc["invertido_historico"] <= 0:
                # Sigue teniendo posición, o nunca se llegó a comprar nada
                # (solo Script-venta/Dividendo, no aplica aquí).
                continue
            valor = session.get(Valor, id_valor)
            if valor is None:
                continue
            sector = session.get(Sector, valor.id_sector)
            resultado = (
                acc["importe_ventas_acumulado"]
                + acc["venta_derechos_acumulada"]
                - acc["invertido_historico"]
            )
            filas.append(
                {
                    "id_valor": id_valor,
                    "ticker": valor.ticker,
                    "mercado": valor.mercado,
                    "empresa": valor.empresa,
                    "zona": valor.zona,
                    "supersector": sector.supersector if sector else "",
                    "sector": sector.sector if sector else "",
                    "fecha_ultima_operacion": acc["fecha_ultima_operacion"],
                    "fecha_ultima_operacion_mostrar": acc["fecha_ultima_operacion"].strftime(
                        "%d/%m/%Y"
                    ),
                    "invertido_historico_mostrar": formatear_eur(acc["invertido_historico"]),
                    "dividendos_acumulados_mostrar": formatear_eur(acc["dividendos_acumulados"]),
                    "venta_derechos_acumulada_mostrar": formatear_eur(
                        acc["venta_derechos_acumulada"]
                    ),
                    "resultado_mostrar": formatear_eur(resultado),
                    "color_resultado": gain_loss_color(resultado),
                }
            )
        filas.sort(key=lambda f: f["fecha_ultima_operacion"], reverse=True)
        for fila in filas:
            del fila["fecha_ultima_operacion"]
        return filas


def obtener_valores_en_cartera(id_cartera: int) -> list[dict]:
    """{id_valor, ticker, mercado, moneda} de los valores con saldo > 0 en
    esta cartera: la lista mínima que necesita `refrescar_cotizaciones`
    (no hace falta traer más columnas solo para pedir el precio)."""
    tenencias = obtener_tenencias(id_cartera)
    return [
        {"id_valor": f["id_valor"], "ticker": f["ticker"], "mercado": f["mercado"], "moneda": f["moneda"]}
        for f in tenencias
    ]


def guardar_cotizacion(id_valor: int, cotizacion_divisa: float, cotizacion_eur: float, actualizada_en) -> None:
    with rx.session() as session:
        valor = session.get(Valor, id_valor)
        if valor is None:
            return
        valor.cotizacion_divisa = cotizacion_divisa
        valor.cotizacion_eur = cotizacion_eur
        valor.cotizacion_actualizada_en = actualizada_en
        session.add(valor)
        session.commit()


def obtener_brokers_con_id() -> list[dict]:
    with rx.session() as session:
        return [
            {"id": b.id, "nombre": b.nombre}
            for b in session.exec(sqlmodel.select(Broker)).all()
        ]


def crear_broker(nombre: str) -> int:
    with rx.session() as session:
        broker = Broker(nombre=nombre)
        session.add(broker)
        session.commit()
        session.refresh(broker)
        return broker.id


def obtener_existencias_broker(id_broker: int) -> list[dict]:
    """Nº de títulos depositados en este bróker, sumando TODAS las
    carteras (Largo Plazo + Corto Plazo): pensado para poder cuadrar
    contra el extracto real del bróker, que no sabe nada de esa
    distinción interna."""
    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_broker == id_broker)
        ).all()

        titulos_por_valor: dict[int, float] = {}
        for op in operaciones:
            if op.tipo_operacion == "Venta":
                titulos_por_valor[op.id_valor] = titulos_por_valor.get(op.id_valor, 0.0) - op.num_titulos
            elif _aporta_titulos(op):
                titulos_por_valor[op.id_valor] = titulos_por_valor.get(op.id_valor, 0.0) + op.num_titulos

        filas = []
        for id_valor, titulos in titulos_por_valor.items():
            if titulos <= 0:
                continue
            valor = session.get(Valor, id_valor)
            if valor is None:
                continue
            filas.append(
                {
                    "ticker": valor.ticker,
                    "mercado": valor.mercado,
                    "empresa": valor.empresa,
                    "num_titulos": titulos,
                    "num_titulos_mostrar": formatear_titulos(titulos),
                }
            )
        return sorted(filas, key=lambda f: f["ticker"])

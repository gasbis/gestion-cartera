"""TWR (rentabilidad ponderada por tiempo) de una cartera y de un valor,
y mantenimiento de los cierres diarios que necesita.

Qué mide (ver también la página Ayuda): la rentabilidad de lo que se
tiene invertido, SIN el efecto de cuándo se aportó o se retiró dinero.
Es la medida justa para compararse con un índice o con un fondo. La TIR
de la app, en cambio, mide lo que ha rendido cada euro aportado (sí
depende del momento de las aportaciones).

Cómo se calcula (TWR "exacta", sin aproximaciones mensuales): el tiempo
se parte en tramos que acaban en cada día con algún movimiento de dinero
(compra, venta, dividendo, prima, derechos...) y en el día de hoy. En
cada tramo:

    R = (V_día + dinero que SALE ese día - dinero que ENTRA ese día) / V_anterior - 1

  - V = valor de los títulos que se tienen al cierre de ese día
    (títulos x cotización de cierre, ver models.CierreDiario; hoy, la
    cotización actual de la app). Los movimientos se consideran hechos
    al final del día.
  - Dinero que sale: ventas, dividendos, primas, derechos vendidos --
    así un dividendo cuenta como rentabilidad.
  - Dinero que entra: compras y derechos comprados.
Entre dos movimientos la rentabilidad de cada día se encadena sola
(V_hoy / V_ayer x V_ayer / V_anteayer...), así que basta con valorar la
cartera esos días. Los tramos se encadenan: TWR = (1+R1) x (1+R2) ... - 1.

Los dividendos y la venta de derechos cuentan en BRUTO (igual que la
TIR); los títulos recibidos en scrip cuentan porque aumentan el número
de títulos y, con ello, el valor.

Si a un valor le falta el cierre de algún día (valor excluido de bolsa,
festivo en su mercado, o cierres aún sin descargar), se usa su último
precio conocido: el último cierre guardado o el de sus propias
compras/ventas.
"""

import bisect
import time
from collections import defaultdict
from datetime import date, timedelta

import reflex as rx
import sqlmodel

from gestion_cartera.cartera_db import _PRIORIDAD_MISMO_DIA, _flujo_caja_operacion
from gestion_cartera.format_utils import formatear_pct
from gestion_cartera.models import CierreDiario, Operacion, Valor
from gestion_cartera.styles import gain_loss_color

# Margen de prudencia entre peticiones a Yahoo Finance (mismo criterio
# que services/radar_scheduler.PAUSA_ENTRE_COTIZACIONES).
PAUSA_ENTRE_VALORES = 1


def _delta_titulos(op: Operacion) -> float:
    """Mismo criterio que operaciones_db.calcular_saldo /
    cartera_db.obtener_existencias_broker."""
    if op.tipo_operacion in ("Venta", "Contrasplit"):
        return -op.num_titulos
    if op.tipo_operacion in ("Compra", "Script", "Split", "Spinoff"):
        return op.num_titulos
    return 0.0


def _salida_de_dinero(op: Operacion, incluir_spinoff: bool) -> float:
    """Dinero que SALE de la posición hacia el inversor con esta
    operación (negativo si entra): el flujo de caja de la TIR
    (cartera_db._flujo_caja_operacion) más la fracción de un
    Split/Contrasplit cobrada o pagada en efectivo."""
    salida = _flujo_caja_operacion(op, incluir_spinoff=incluir_spinoff)
    if op.tipo_operacion in ("Split", "Contrasplit") and op.importe:
        if op.tipo_ajuste_fraccion == "Venta":
            salida += op.importe
        elif op.tipo_ajuste_fraccion == "Compra":
            salida -= op.importe
    return salida


# --- Cierres diarios -----------------------------------------------------


def tramos_pendientes(hoy: date | None = None) -> dict[int, tuple[date, date]]:
    """{id_valor: (desde, hasta)} con los días que faltan por descargar
    de cada valor: desde el día siguiente al último guardado (o desde su
    primera operación) hasta ayer -- o hasta su última operación, si ya
    no se tiene en ninguna cartera."""
    hoy = hoy or date.today()
    ayer = hoy - timedelta(days=1)

    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(
                Operacion.id_valor, Operacion.fecha, Operacion.tipo_operacion, Operacion.num_titulos
            )
        ).all()
        ultimos = dict(
            session.exec(
                sqlmodel.select(CierreDiario.id_valor, sqlmodel.func.max(CierreDiario.fecha)).group_by(
                    CierreDiario.id_valor
                )
            ).all()
        )

    primera: dict[int, date] = {}
    ultima_op: dict[int, date] = {}
    titulos: dict[int, float] = defaultdict(float)
    for id_valor, fecha, tipo, num in operaciones:
        primera[id_valor] = min(primera.get(id_valor, fecha), fecha)
        ultima_op[id_valor] = max(ultima_op.get(id_valor, fecha), fecha)
        if tipo in ("Venta", "Contrasplit"):
            titulos[id_valor] -= num
        elif tipo in ("Compra", "Script", "Split", "Spinoff"):
            titulos[id_valor] += num

    pendientes = {}
    for id_valor, inicio in primera.items():
        hasta = ayer if titulos[id_valor] > 1e-9 else min(ultima_op[id_valor], ayer)
        desde = ultimos[id_valor] + timedelta(days=1) if id_valor in ultimos else inicio
        if desde <= hasta:
            pendientes[id_valor] = (desde, hasta)
    return pendientes


def actualizar_cierres_pendientes(hoy: date | None = None, aplicar: bool = True) -> dict:
    """Descarga de Yahoo Finance y guarda los cierres diarios que falten
    (ver `tramos_pendientes`). Si Yahoo no tiene ningún dato de un tramo,
    se guarda una única fila sin cierre al final del tramo, para no
    volver a pedirlo. Bloqueante: lo llaman el chequeo automático diario
    (en su propio hilo) y preparar_historicos.py. Con `aplicar=False`
    solo cuenta lo que haría. Devuelve {"valores", "cierres", "sin_dato"}."""
    from gestion_cartera.services.yahoo_finance import obtener_cierres_diarios_eur

    pendientes = tramos_pendientes(hoy)
    resumen = {"valores": len(pendientes), "cierres": 0, "sin_dato": 0}
    if not aplicar:
        return resumen

    for i, (id_valor, (desde, hasta)) in enumerate(pendientes.items()):
        with rx.session() as session:
            valor = session.get(Valor, id_valor)
        if valor is None:
            continue
        try:
            cierres = obtener_cierres_diarios_eur(valor.ticker, valor.moneda, valor.mercado, desde, hasta)
        except Exception as e:  # red, símbolo desconocido...: se reintenta otro día
            print(f"[TWR] No se pudieron descargar los cierres de {valor.ticker}: {e}")
            continue
        with rx.session() as session:
            if cierres:
                for fecha, cierre in cierres.items():
                    session.add(CierreDiario(id_valor=id_valor, fecha=fecha, cierre_eur=cierre))
                resumen["cierres"] += len(cierres)
            else:
                session.add(CierreDiario(id_valor=id_valor, fecha=hasta, cierre_eur=None))
                resumen["sin_dato"] += 1
            session.commit()
        print(f"[TWR] {valor.ticker}: {len(cierres)} cierres guardados ({desde} a {hasta}).")
        if i < len(pendientes) - 1:
            time.sleep(PAUSA_ENTRE_VALORES)
    return resumen


# --- Cálculo -------------------------------------------------------------


def calcular_twr(id_cartera: int, id_valor: int | None = None, hoy: date | None = None) -> dict | None:
    """TWR de la cartera (o solo de `id_valor` dentro de ella) desde su
    primera operación hasta hoy. None si no hay operaciones.
    {"total": 1.57, "anual": 0.106 | None (menos de un año de
    historia), "desde": date, "anios": 9.3}"""
    hoy = hoy or date.today()
    with rx.session() as session:
        consulta = sqlmodel.select(Operacion).where(Operacion.id_cartera == id_cartera)
        if id_valor is not None:
            consulta = consulta.where(Operacion.id_valor == id_valor)
        operaciones = [op for op in session.exec(consulta).all() if op.fecha <= hoy]
        if not operaciones:
            return None
        ids = list({op.id_valor for op in operaciones})
        cotizaciones = dict(
            session.exec(sqlmodel.select(Valor.id, Valor.cotizacion_eur).where(Valor.id.in_(ids))).all()
        )
        cierres = session.exec(
            sqlmodel.select(CierreDiario.id_valor, CierreDiario.fecha, CierreDiario.cierre_eur).where(
                CierreDiario.id_valor.in_(ids), CierreDiario.cierre_eur.is_not(None)
            )
        ).all()

    operaciones.sort(key=lambda op: (op.fecha, _PRIORIDAD_MISMO_DIA.get(op.tipo_operacion, 1)))

    # Precios conocidos de cada valor: los de sus compras/ventas, los
    # cierres diarios (que prevalecen) y la cotización actual (hoy).
    puntos: dict[int, dict[date, float]] = defaultdict(dict)
    for op in operaciones:
        if op.tipo_operacion in ("Compra", "Venta") and op.importe_unitario and op.importe_unitario > 0:
            puntos[op.id_valor][op.fecha] = op.importe_unitario
    for id_v, fecha, cierre in cierres:
        puntos[id_v][fecha] = cierre
    for id_v, cotizacion in cotizaciones.items():
        if cotizacion:
            puntos[id_v][hoy] = cotizacion
    tablas = {}
    for id_v, p in puntos.items():
        fechas = sorted(p)
        tablas[id_v] = (fechas, [p[f] for f in fechas])

    def precio(id_v: int, fecha: date) -> float:
        fechas, precios = tablas.get(id_v, ([], []))
        if not fechas:
            return 0.0
        i = bisect.bisect_right(fechas, fecha) - 1
        return precios[max(i, 0)]

    por_dia: dict[date, list[Operacion]] = defaultdict(list)
    for op in operaciones:
        por_dia[op.fecha].append(op)
    dias = sorted(por_dia)
    if dias[-1] < hoy:
        dias.append(hoy)

    titulos: dict[int, float] = defaultdict(float)
    nivel = 1.0
    valor_anterior = 0.0
    for dia in dias:
        salida = 0.0
        for op in por_dia.get(dia, []):
            titulos[op.id_valor] += _delta_titulos(op)
            salida += _salida_de_dinero(op, incluir_spinoff=id_valor is not None)
        valor_dia = sum(t * precio(v, dia) for v, t in titulos.items() if t > 1e-9)
        if valor_anterior > 1e-6:
            nivel *= (valor_dia + salida) / valor_anterior
        valor_anterior = valor_dia

    inicio = operaciones[0].fecha
    anios = (hoy - inicio).days / 365.25
    anual = (nivel ** (1 / anios) - 1) if anios >= 1 and nivel > 0 else None
    return {"total": nivel - 1, "anual": anual, "desde": inicio, "anios": anios}


def twr_mostrar(resultado: dict | None) -> dict:
    """Textos y color para la tarjeta de TWR (Inicio y detalle de
    valor): anualizada si hay al menos un año de historia; si no, solo
    el total, sin anualizar (anualizar unos pocos meses exagera)."""
    if resultado is None:
        return {"twr_mostrar": "—", "twr_secundario": "", "color_twr": "var(--gray-9)"}
    desde = resultado["desde"].strftime("%m/%Y")
    total = formatear_pct(round(resultado["total"] * 100, 2))
    if resultado["anual"] is None:
        return {
            "twr_mostrar": total,
            "twr_secundario": f"Total desde {desde} (menos de un año, sin anualizar)",
            "color_twr": gain_loss_color(resultado["total"]),
        }
    return {
        "twr_mostrar": f"{formatear_pct(round(resultado['anual'] * 100, 2))} anual",
        "twr_secundario": f"Total: {total} desde {desde}",
        "color_twr": gain_loss_color(resultado["anual"]),
    }

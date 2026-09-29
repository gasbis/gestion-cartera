"""Consultas de base de datos para la página VALOR (detalle de un único
valor dentro de la cartera seleccionada): resumen, rentabilidad por año
y operaciones agrupadas por año. Reutiliza la misma lógica de coste
medio ponderado / reinicio en liquidación total y las mismas TIR que
cartera_db.py, pero aplicadas solo a las operaciones de este valor.
"""

from collections import defaultdict
from datetime import date

import reflex as rx
import sqlmodel

from gestion_cartera.cartera_db import (
    _PRIORIDAD_MISMO_DIA,
    _aporta_coste,
    _aporta_titulos,
    _flujo_caja_operacion,
    _xirr,
    PosicionFIFO,
    aplicar_spinoff,
    aplicar_split_y_fraccion,
)
from gestion_cartera.format_utils import formatear_eur, formatear_pct, formatear_titulos
from gestion_cartera.models import Operacion, RadarCandidato, Sector, Valor
from gestion_cartera.services.company_logo import obtener_logo_url
from gestion_cartera.services.yahoo_finance import SUFIJO_YAHOO
from gestion_cartera.styles import gain_loss_color

# Mercados admitidos (los mismos para los que sabemos traducir a Yahoo
# Finance, ver services/yahoo_finance.SUFIJO_YAHOO): se reutiliza esa
# lista para el selector de "editar ticker/mercado" en vez de duplicarla.
MERCADOS = list(SUFIJO_YAHOO.keys())


def actualizar_ticker_mercado(id_valor: int, nuevo_ticker: str, nuevo_mercado: str) -> str | None:
    """Cambia el ticker y/o el mercado de un Valor ya existente -- por
    ejemplo, tras un cambio de símbolo bursátil o un traslado de
    cotización a otro mercado. El resto de la app siempre referencia al
    valor por su `id` (Operacion.id_valor), así que el cambio se refleja
    automáticamente en TODO el histórico de operaciones sin tocar
    ninguna fila de Operacion.

    También limpia la cotización en caché (correspondía al ticker/
    mercado ANTIGUO, que con el símbolo nuevo ya no tiene sentido): la
    próxima vez que se pida la cotización en vivo se pedirá ya con el
    símbolo correcto.

    Devuelve un mensaje de error si el ticker+mercado nuevo ya lo usa
    otro Valor (mismo motivo que al dar de alta uno, ver
    operaciones_db.crear_valor), o None si se ha guardado bien."""
    with rx.session() as session:
        valor = session.get(Valor, id_valor)
        if valor is None:
            return "No se ha encontrado el valor."

        duplicado = session.exec(
            sqlmodel.select(Valor).where(
                Valor.ticker == nuevo_ticker,
                Valor.mercado == nuevo_mercado,
                Valor.id != id_valor,
            )
        ).first()
        if duplicado is not None:
            return (
                f"Ya existe otro valor con el ticker «{nuevo_ticker}» en el mercado "
                f"«{nuevo_mercado}» ({duplicado.empresa})."
            )

        valor.ticker = nuevo_ticker
        valor.mercado = nuevo_mercado
        valor.cotizacion_divisa = None
        valor.cotizacion_eur = None
        valor.cotizacion_actualizada_en = None
        session.add(valor)
        session.commit()
    return None


def obtener_valor_duplicado(id_valor: int, ticker: str, mercado: str) -> dict | None:
    """Si ya hay OTRO Valor con ese ticker+mercado, devuelve sus datos
    básicos ({id, ticker, mercado, empresa}); si no, None. Lo usa el
    diálogo de editar ticker/mercado para ofrecer la fusión en lugar de
    quedarse bloqueado con un error."""
    with rx.session() as session:
        duplicado = session.exec(
            sqlmodel.select(Valor).where(
                Valor.ticker == ticker,
                Valor.mercado == mercado,
                Valor.id != id_valor,
            )
        ).first()
        if duplicado is None:
            return None
        return {
            "id": duplicado.id,
            "ticker": duplicado.ticker,
            "mercado": duplicado.mercado,
            "empresa": duplicado.empresa,
        }


def fusionar_valores(id_origen: int, id_destino: int) -> str | None:
    """Fusiona el Valor `id_origen` DENTRO de `id_destino`: todas las
    referencias al origen pasan a apuntar al destino y el origen se
    borra. Pensado para el caso en que el mismo valor ha acabado dado
    de alta dos veces con distinto mercado/ticker (p. ej. porque una
    importación de Excel usó otro mercado, o porque un usuario cambió
    el mercado y otro dio de alta el valor de nuevo con el mercado
    viejo). Como las tenencias se calculan siempre a partir de las
    operaciones, no hay nada más que recalcular.

    Referencias que se reasignan (todas en la misma transacción):
    - Operacion.id_valor
    - Operacion.id_valor_relacionado (enlace de Spinoff)
    - RadarCandidato.id_valor -- si el mismo usuario ya tiene el
      destino en la misma lista, se conserva el del destino y se borra
      el del origen (restricción única usuario+valor+lista).

    Devuelve un mensaje de error, o None si ha ido bien."""
    if id_origen == id_destino:
        return "No se puede fusionar un valor consigo mismo."
    with rx.session() as session:
        origen = session.get(Valor, id_origen)
        destino = session.get(Valor, id_destino)
        if origen is None or destino is None:
            return "No se ha encontrado alguno de los dos valores."

        for op in session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_valor == id_origen)
        ).all():
            op.id_valor = id_destino
            session.add(op)

        for op in session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_valor_relacionado == id_origen)
        ).all():
            op.id_valor_relacionado = id_destino
            session.add(op)

        for cand in session.exec(
            sqlmodel.select(RadarCandidato).where(RadarCandidato.id_valor == id_origen)
        ).all():
            ya_existe = session.exec(
                sqlmodel.select(RadarCandidato).where(
                    RadarCandidato.id_usuario == cand.id_usuario,
                    RadarCandidato.id_valor == id_destino,
                    RadarCandidato.tipo_lista == cand.tipo_lista,
                )
            ).first()
            if ya_existe is not None:
                session.delete(cand)
            else:
                cand.id_valor = id_destino
                session.add(cand)

        # Aplicar los cambios de las filas hijas antes de borrar el
        # Valor, para que la clave foránea no lo impida.
        session.flush()
        session.delete(origen)
        session.commit()
    return None


def obtener_resumen_valor(id_cartera: int, id_valor: int) -> dict | None:
    """Cabecera + números grandes del valor: posición actual, plusvalía
    (coste de los lotes que TODAVÍA se poseen, valorados por FIFO -- ver
    cartera_db.PosicionFIFO), TIR individual (mismo método que la TIR de
    cartera -- con y sin revalorización, ver cartera_db.calcular_tir --
    pero solo con los flujos de este valor) y dividendos + venta de
    derechos acumulados en todo el histórico."""
    with rx.session() as session:
        valor = session.get(Valor, id_valor)
        if valor is None:
            return None
        sector = session.get(Sector, valor.id_sector)
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(
                Operacion.id_cartera == id_cartera, Operacion.id_valor == id_valor
            )
        ).all()

    operaciones = sorted(
        operaciones, key=lambda op: (op.fecha, _PRIORIDAD_MISMO_DIA.get(op.tipo_operacion, 1))
    )

    posicion = PosicionFIFO()
    dividendos_acumulados = 0.0
    venta_derechos_acumulada = 0.0

    for op in operaciones:
        if op.tipo_operacion == "Venta":
            posicion.vender(op.num_titulos)
        elif op.tipo_operacion == "Prima":
            posicion.aplicar_prima(op.importe)
        elif op.tipo_operacion in ("Split", "Contrasplit"):
            aplicar_split_y_fraccion(posicion, op)
        elif op.tipo_operacion == "Spinoff":
            aplicar_spinoff(posicion, op)
        elif _aporta_titulos(op):
            coste_unitario = (
                (op.importe / op.num_titulos) if _aporta_coste(op) and op.num_titulos else 0.0
            )
            posicion.comprar(op.num_titulos, coste_unitario)

        if op.tipo_operacion == "Dividendo":
            dividendos_acumulados += op.importe
        elif op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta":
            venta_derechos_acumulada += op.importe

    titulos = posicion.titulos
    valor_compra = posicion.coste_total if titulos > 0 else 0.0
    precio_medio = valor_compra / titulos if titulos > 0 else 0.0
    cotizacion = valor.cotizacion_eur or 0.0
    valor_mercado = cotizacion * titulos if titulos > 0 else 0.0
    plusvalia_eur = valor_mercado - valor_compra
    plusvalia_pct = (plusvalia_eur / valor_compra * 100) if valor_compra else 0.0

    flujos = [
        (op.fecha, importe) for op in operaciones if (importe := _flujo_caja_operacion(op, incluir_spinoff=True)) != 0.0
    ]
    hoy = date.today()
    tir_con = _xirr(flujos + [(hoy, valor_mercado)]) if flujos else None
    tir_sin = _xirr(flujos + [(hoy, valor_compra)]) if flujos else None

    return {
        "id_valor": id_valor,
        "ticker": valor.ticker,
        "empresa": valor.empresa,
        "logo_url": obtener_logo_url(valor.ticker, valor.mercado),
        "mercado": valor.mercado,
        "zona": valor.zona,
        "moneda": valor.moneda,
        "supersector": sector.supersector if sector else "",
        "sector": sector.sector if sector else "",
        "grupo": sector.grupo if sector else "",
        "cotizacion_actual_mostrar": formatear_eur(cotizacion),
        "cotizacion_actualizada_en": (
            valor.cotizacion_actualizada_en.strftime("%d/%m/%Y %H:%M")
            if valor.cotizacion_actualizada_en
            else ""
        ),
        "num_titulos_mostrar": formatear_titulos(titulos) if titulos > 0 else "0",
        "valor_compra_mostrar": formatear_eur(valor_compra),
        "precio_medio_mostrar": formatear_eur(precio_medio),
        "valor_mercado_mostrar": formatear_eur(valor_mercado),
        "plusvalia_eur_mostrar": formatear_eur(plusvalia_eur),
        "plusvalia_pct_mostrar": formatear_pct(plusvalia_pct),
        "color_plusvalia": gain_loss_color(plusvalia_eur),
        "tir_con_revalorizacion_mostrar": (
            formatear_pct(round(tir_con * 100, 2)) if tir_con is not None else "—"
        ),
        "tir_sin_revalorizacion_mostrar": (
            formatear_pct(round(tir_sin * 100, 2)) if tir_sin is not None else "—"
        ),
        "dividendos_acumulados_mostrar": formatear_eur(dividendos_acumulados),
        "venta_derechos_acumulada_mostrar": formatear_eur(venta_derechos_acumulada),
        "total_ingresos_mostrar": formatear_eur(dividendos_acumulados + venta_derechos_acumulada),
        "tiene_posicion": titulos > 0,
    }


def obtener_rentabilidad_por_anio(id_cartera: int, id_valor: int) -> list[dict]:
    """Una fila por año natural desde la primera operación de este valor
    hasta hoy: títulos y precio medio "a cierre" (31/12 de ese año, o
    hoy para el año en curso), dividendos + venta de derechos cobrados
    ESE año, YOC (sobre el valor de compra a cierre) y R.D. (sobre la
    cotización actual, siempre -- ver cartera_db para el porqué)."""
    with rx.session() as session:
        valor = session.get(Valor, id_valor)
        if valor is None:
            return []
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(
                Operacion.id_cartera == id_cartera, Operacion.id_valor == id_valor
            )
        ).all()
    if not operaciones:
        return []
    operaciones = sorted(
        operaciones, key=lambda op: (op.fecha, _PRIORIDAD_MISMO_DIA.get(op.tipo_operacion, 1))
    )

    cotizacion_actual = valor.cotizacion_eur or 0.0
    hoy = date.today()
    anio_actual = hoy.year
    anio_inicio = operaciones[0].fecha.year

    posicion = PosicionFIFO()
    dividendos_por_anio: dict[int, float] = defaultdict(float)

    idx = 0
    n = len(operaciones)
    filas = []
    for anio in range(anio_inicio, anio_actual + 1):
        fecha_corte = date(anio, 12, 31) if anio < anio_actual else hoy
        while idx < n and operaciones[idx].fecha <= fecha_corte:
            op = operaciones[idx]
            if op.tipo_operacion == "Venta":
                posicion.vender(op.num_titulos)
            elif op.tipo_operacion == "Prima":
                posicion.aplicar_prima(op.importe)
            elif op.tipo_operacion in ("Split", "Contrasplit"):
                aplicar_split_y_fraccion(posicion, op)
            elif op.tipo_operacion == "Spinoff":
                aplicar_spinoff(posicion, op)
            elif _aporta_titulos(op):
                coste_unitario = (
                    (op.importe / op.num_titulos)
                    if _aporta_coste(op) and op.num_titulos
                    else 0.0
                )
                posicion.comprar(op.num_titulos, coste_unitario)

            if op.tipo_operacion == "Dividendo":
                dividendos_por_anio[op.fecha.year] += op.importe
            elif op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta":
                dividendos_por_anio[op.fecha.year] += op.importe
            idx += 1

        titulos = posicion.titulos
        precio_medio_cierre = posicion.coste_total / titulos if titulos > 0 else 0.0
        valor_compra_cierre = posicion.coste_total if titulos > 0 else 0.0
        dividendos_anio = dividendos_por_anio.get(anio, 0.0)
        yoc = (dividendos_anio / valor_compra_cierre * 100) if valor_compra_cierre else 0.0
        rd = (
            (dividendos_anio / (cotizacion_actual * titulos) * 100)
            if cotizacion_actual and titulos > 0
            else 0.0
        )

        # Solo se muestran años con posición o con algún dividendo/derecho.
        if titulos > 1e-9 or dividendos_anio:
            filas.append(
                {
                    "anio": anio,
                    "titulos_cierre_mostrar": formatear_titulos(titulos),
                    "precio_medio_cierre_mostrar": formatear_eur(precio_medio_cierre),
                    "dividendos_anio_mostrar": formatear_eur(dividendos_anio),
                    "yoc_mostrar": formatear_pct(round(yoc, 2)),
                    "rd_mostrar": formatear_pct(round(rd, 2)),
                }
            )
    return list(reversed(filas))


def obtener_operaciones_por_anio(id_cartera: int, id_valor: int) -> list[dict]:
    """Agregado anual de Compra / Script-compra / Script-venta (títulos e
    importe), para ver de un vistazo cuánto se ha movido cada año.

    Spinoff va en su propia columna (no como Compra, para que se vea de
    dónde salen esos títulos): en la filial, títulos recibidos y coste
    asignado (+); en la matriz, 0 títulos y el coste traspasado a la
    filial en negativo (-). El importe de la filial es el de los títulos
    TEÓRICOS: si la fracción se cobró en efectivo, esa fracción se vende
    aparte (Venta), así que la inversión viva del valor puede ser algo
    menor."""
    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(
                Operacion.id_cartera == id_cartera, Operacion.id_valor == id_valor
            )
        ).all()

    por_anio: dict[int, dict] = defaultdict(
        lambda: {
            "compra_titulos": 0.0,
            "compra_importe": 0.0,
            "script_cpa_titulos": 0.0,
            "script_cpa_importe": 0.0,
            "script_venta_titulos": 0.0,
            "script_venta_importe": 0.0,
            "spinoff_titulos": 0.0,
            "spinoff_importe": 0.0,
        }
    )
    for op in operaciones:
        anio = op.fecha.year
        acc = por_anio[anio]
        if op.tipo_operacion == "Spinoff":
            if op.num_titulos > 0:
                acc["spinoff_titulos"] += op.num_titulos
                acc["spinoff_importe"] += op.importe
            else:
                acc["spinoff_importe"] -= op.importe or 0.0
        elif op.tipo_operacion == "Compra":
            acc["compra_titulos"] += op.num_titulos
            acc["compra_importe"] += op.importe
        elif op.tipo_operacion == "Script" and op.tipo_derecho_script == "Compra":
            acc["script_cpa_titulos"] += op.num_titulos
            acc["script_cpa_importe"] += op.importe
        elif op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta":
            acc["script_venta_titulos"] += op.num_titulos
            acc["script_venta_importe"] += op.importe

    filas = []
    for anio, acc in sorted(por_anio.items(), reverse=True):
        total_titulos = (
            acc["compra_titulos"]
            + acc["script_cpa_titulos"]
            + acc["script_venta_titulos"]
            + acc["spinoff_titulos"]
        )
        total_importe = (
            acc["compra_importe"]
            + acc["script_cpa_importe"]
            + acc["script_venta_importe"]
            + acc["spinoff_importe"]
        )
        if not any(acc.values()):
            continue
        filas.append(
            {
                "anio": anio,
                "compra_titulos_mostrar": formatear_titulos(acc["compra_titulos"]),
                "compra_importe_mostrar": formatear_eur(acc["compra_importe"]),
                "script_cpa_titulos_mostrar": formatear_titulos(acc["script_cpa_titulos"]),
                "script_cpa_importe_mostrar": formatear_eur(acc["script_cpa_importe"]),
                "script_venta_titulos_mostrar": formatear_titulos(acc["script_venta_titulos"]),
                "script_venta_importe_mostrar": formatear_eur(acc["script_venta_importe"]),
                "spinoff_titulos_mostrar": formatear_titulos(acc["spinoff_titulos"]),
                "spinoff_importe_mostrar": formatear_eur(acc["spinoff_importe"]),
                "total_titulos_mostrar": formatear_titulos(total_titulos),
                "total_importe_mostrar": formatear_eur(total_importe),
            }
        )
    return filas

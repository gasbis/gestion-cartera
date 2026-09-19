"""Consultas de base de datos para la página principal (resumen general
de la cartera seleccionada): cifras agregadas, top-5 de revalorización y
de YOC, dividendos por año (histórico completo, todos los valores) y
distribución por zona/supersector (valor de compra vs. valor actual,
solo tenencias vivas).
"""

from collections import defaultdict

import reflex as rx
import sqlmodel

from gestion_cartera.cartera_db import calcular_tir, obtener_tenencias
from gestion_cartera.format_utils import formatear_eur, formatear_pct
from gestion_cartera.models import Operacion
from gestion_cartera.styles import gain_loss_color


def obtener_fecha_ultima_operacion(id_cartera: int) -> str:
    with rx.session() as session:
        op = session.exec(
            sqlmodel.select(Operacion)
            .where(Operacion.id_cartera == id_cartera)
            .order_by(Operacion.fecha.desc())
        ).first()
        return op.fecha.strftime("%d/%m/%Y") if op else "—"


_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def obtener_fecha_primera_operacion_mostrar(id_cartera: int) -> str | None:
    """Mes y año de la operación más antigua de la cartera (p.ej.
    "enero 2020"), para la línea "Propiedad de ... iniciada en ..." del
    header. None si la cartera no tiene ninguna operación todavía."""
    with rx.session() as session:
        op = session.exec(
            sqlmodel.select(Operacion)
            .where(Operacion.id_cartera == id_cartera)
            .order_by(Operacion.fecha.asc())
        ).first()
        if op is None:
            return None
        return f"{_MESES_ES[op.fecha.month - 1]} {op.fecha.year}"


def obtener_resumen_general(id_cartera: int) -> dict:
    """Cifras agregadas de la cartera: valor de compra, valor actual,
    saldo (diferencia €/%) y TIR con/sin revalorización (mismas fórmulas
    que en cartera_db.py)."""
    tenencias = obtener_tenencias(id_cartera)
    valor_compra_total = round(sum(f["valor_compra"] for f in tenencias), 2)
    valor_mercado_total = round(sum(f["valor_mercado"] for f in tenencias), 2)
    saldo_eur = round(valor_mercado_total - valor_compra_total, 2)
    saldo_pct = round(saldo_eur / valor_compra_total * 100, 2) if valor_compra_total else 0.0

    tir = calcular_tir(id_cartera)
    tir_con = tir["con_revalorizacion"]
    tir_sin = tir["sin_revalorizacion"]
    tir_con_mostrar = formatear_pct(tir_con) if tir_con is not None else "—"
    tir_sin_mostrar = formatear_pct(tir_sin) if tir_sin is not None else "—"

    return {
        "valor_compra_mostrar": formatear_eur(valor_compra_total),
        "valor_mercado_mostrar": formatear_eur(valor_mercado_total),
        "saldo_eur_mostrar": formatear_eur(saldo_eur),
        "saldo_pct_mostrar": formatear_pct(saldo_pct),
        "color_saldo": gain_loss_color(saldo_eur),
        "tir_con_mostrar": tir_con_mostrar,
        "tir_sin_mostrar": f"Sin revalorización: {tir_sin_mostrar}",
        "color_tir": gain_loss_color(tir_con if tir_con is not None else 0.0),
        "numero_valores": len(tenencias),
        "fecha_ultima_operacion_mostrar": obtener_fecha_ultima_operacion(id_cartera),
    }


def obtener_top_valores(id_cartera: int) -> dict:
    """Top-5 de cada tabla de la página principal, reutilizando los
    campos ya calculados/formateados por `obtener_tenencias` (no hace
    falta volver a formatear nada aquí). En las de revalorización el %
    lleva color (verde/rojo) igual que en el resto de la app; en las de
    YOC no -- es una magnitud, no una ganancia/pérdida con signo."""
    tenencias = obtener_tenencias(id_cartera)

    def top(campo: str, campo_mostrar: str, descendente: bool, con_color: bool) -> list[dict]:
        ordenado = sorted(tenencias, key=lambda f: f[campo], reverse=descendente)[:5]
        return [
            {
                "ticker": f["ticker"],
                "empresa": f["empresa"],
                "valor_mostrar": f[campo_mostrar],
                "color": gain_loss_color(f[campo]) if con_color else "var(--gray-12)",
            }
            for f in ordenado
        ]

    return {
        "mejor_revalorizacion": top("plusvalia_pct", "plusvalia_pct_mostrar", True, True),
        "peor_revalorizacion": top("plusvalia_pct", "plusvalia_pct_mostrar", False, True),
        "mejor_yoc": top("yoc_anterior", "yoc_anterior_mostrar", True, False),
        "peor_yoc": top("yoc_anterior", "yoc_anterior_mostrar", False, False),
    }


def obtener_dividendos_por_anio(id_cartera: int) -> list[dict]:
    """Dividendos + venta de derechos (Script con derecho VENDIDO) de
    TODA la cartera, año a año, con el histórico completo (incluye
    valores ya liquidados del todo). Formato listo para `rx.recharts`:
    [{"name": "2020", "uv": 123.45}, ...]."""
    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_cartera == id_cartera)
        ).all()

    por_anio: dict[int, float] = defaultdict(float)
    for op in operaciones:
        if op.tipo_operacion == "Dividendo":
            por_anio[op.fecha.year] += op.importe
        elif op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta":
            por_anio[op.fecha.year] += op.importe

    if not por_anio:
        return []
    anio_min, anio_max = min(por_anio), max(por_anio)
    return [
        {
            "name": str(anio),
            "uv": round(por_anio.get(anio, 0.0), 2),
            # Etiqueta ya formateada para mostrar encima de cada barra sin
            # tener que pasar el ratón por encima (LabelList la lee de un
            # campo aparte, independiente del que dibuja la altura).
            "uv_mostrar": formatear_eur(por_anio.get(anio, 0.0)),
        }
        for anio in range(anio_min, anio_max + 1)
    ]


def obtener_dividendos_totales_mostrar(dividendos_por_anio: list[dict]) -> str:
    if not dividendos_por_anio:
        return "—"
    return formatear_eur(sum(f["uv"] for f in dividendos_por_anio))


def _distribucion(tenencias: list[dict], campo_grupo: str) -> list[dict]:
    """Una fila por grupo (zona o supersector) comparando el peso por
    valor de compra frente al peso por valor actual -- pensado para un
    gráfico de barras horizontales agrupadas (dos barras por fila, con
    su % ya formateado para poder etiquetarlas sin necesidad de hacer
    hover), ordenado de mayor a menor peso actual."""
    total_compra = sum(f["valor_compra"] for f in tenencias)
    total_mercado = sum(f["valor_mercado"] for f in tenencias)

    grupos_compra: dict[str, float] = defaultdict(float)
    grupos_mercado: dict[str, float] = defaultdict(float)
    for f in tenencias:
        grupos_compra[f[campo_grupo]] += f["valor_compra"]
        grupos_mercado[f[campo_grupo]] += f["valor_mercado"]

    nombres = set(grupos_compra) | set(grupos_mercado)
    filas = []
    for nombre in nombres:
        compra_pct = round(grupos_compra.get(nombre, 0.0) / total_compra * 100, 1) if total_compra else 0.0
        actual_pct = round(grupos_mercado.get(nombre, 0.0) / total_mercado * 100, 1) if total_mercado else 0.0
        filas.append(
            {
                "name": nombre,
                "compra_pct": compra_pct,
                "compra_pct_mostrar": formatear_pct(compra_pct),
                "actual_pct": actual_pct,
                "actual_pct_mostrar": formatear_pct(actual_pct),
            }
        )
    return sorted(filas, key=lambda f: f["actual_pct"], reverse=True)


def obtener_distribucion_zonas(id_cartera: int) -> list[dict]:
    return _distribucion(obtener_tenencias(id_cartera), "zona")


def obtener_distribucion_sectores(id_cartera: int) -> list[dict]:
    return _distribucion(obtener_tenencias(id_cartera), "supersector")

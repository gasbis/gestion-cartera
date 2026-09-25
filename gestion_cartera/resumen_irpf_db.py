"""Consultas de base de datos para la página IRPF: resumen anual pensado
para ayudar a confeccionar la declaración de la renta del año
seleccionado -- dividendos y venta de derechos cobrados con sus
retenciones (en destino, y en origen desglosada entre la parte
"hasta el 15%" y el exceso sobre ese límite) y plusvalías realizadas en
ventas (por lotes FIFO, reutilizando cartera_db.PosicionFIFO).

A diferencia del resto de páginas de la app, aquí se combinan SIEMPRE
las DOS carteras del usuario (Largo Plazo + Corto Plazo): de cara a
Hacienda da igual en qué cartera interna esté cada valor, el resultado
fiscal es uno solo.
"""

from collections import defaultdict
from datetime import date

import reflex as rx
import sqlmodel

from gestion_cartera.cartera_db import (
    PosicionFIFO,
    _aporta_coste,
    _aporta_titulos,
    _PRIORIDAD_MISMO_DIA,
    aplicar_spinoff,
    aplicar_split_y_fraccion,
)
from gestion_cartera.format_utils import formatear_eur, formatear_titulos
from gestion_cartera.models import Operacion, Valor
from gestion_cartera.operaciones_db import obtener_cartera_id
from gestion_cartera.styles import gain_loss_color

# Límite de retención en origen que se considera siempre acreditable en
# la declaración (el típico de los convenios de doble imposición de
# España, 15% sobre el bruto cobrado): lo que un país retenga por
# encima de eso normalmente no es acreditable sin trámite aparte, así
# que conviene verlo identificado por separado, listado por zona/mercado
# (ver `_grupo_origen`).
LIMITE_RETENCION_ORIGEN_ACREDITABLE = 0.15


def _mapa_cartera_tipo(id_usuario: int) -> dict[int, str]:
    """{id_cartera: "Largo Plazo"|"Corto Plazo"} de este usuario -- solo
    las que existan (un usuario recién creado siempre tiene las dos, ver
    auth_db.crear_usuario, pero por seguridad no se asume)."""
    mapa: dict[int, str] = {}
    for tipo in ("Largo Plazo", "Corto Plazo"):
        id_cartera = obtener_cartera_id(id_usuario, tipo)
        if id_cartera is not None:
            mapa[id_cartera] = tipo
    return mapa


def obtener_anios_disponibles(id_usuario: int) -> list[int]:
    """Desde el año de la operación más antigua (en cualquiera de las
    dos carteras) hasta el año actual, de más reciente a más antiguo --
    el orden en que interesa verlos en el selector "Año fiscal"."""
    ids_cartera = list(_mapa_cartera_tipo(id_usuario).keys())
    hoy_anio = date.today().year
    if not ids_cartera:
        return [hoy_anio]
    with rx.session() as session:
        primera = session.exec(
            sqlmodel.select(Operacion)
            .where(Operacion.id_cartera.in_(ids_cartera))
            .order_by(Operacion.fecha.asc())
        ).first()
    anio_inicio = primera.fecha.year if primera else hoy_anio
    return list(range(hoy_anio, anio_inicio - 1, -1))


def _grupo_origen(zona: str, mercado: str | None) -> str:
    """Cómo agrupar el exceso de retención en origen "por países o
    mercados" (a petición expresa): por zona, salvo la zona EURO -- que
    junta países con convenios y retenciones distintas entre sí-- que se
    desglosa por mercado en su lugar."""
    if zona == "EURO":
        return f"EURO · {mercado or 'sin mercado'}"
    return zona or "Sin zona"


def obtener_resumen_irpf(id_usuario: int, anio: int) -> dict:
    mapa_cartera = _mapa_cartera_tipo(id_usuario)
    ids_cartera = list(mapa_cartera.keys())

    if ids_cartera:
        with rx.session() as session:
            operaciones_todas = session.exec(
                sqlmodel.select(Operacion, Valor)
                .where(Operacion.id_cartera.in_(ids_cartera))
                .join(Valor, Operacion.id_valor == Valor.id)
            ).all()
    else:
        operaciones_todas = []

    # --- 1) Dividendos + venta de derechos (Script con derecho vendido) ---
    listado_dividendos = []
    total_bruto = 0.0
    total_retencion_destino = 0.0
    total_origen_hasta15 = 0.0
    total_origen_exceso = 0.0
    exceso_por_grupo: dict[str, float] = defaultdict(float)

    for op, valor in operaciones_todas:
        if op.fecha.year != anio:
            continue
        es_dividendo = op.tipo_operacion == "Dividendo"
        es_script_venta = op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta"
        if not (es_dividendo or es_script_venta):
            continue

        bruto = op.importe
        ret_destino = op.retencion_destino or 0.0
        ret_origen = op.retencion_origen or 0.0
        tope_15 = round(bruto * LIMITE_RETENCION_ORIGEN_ACREDITABLE, 2)
        origen_hasta15 = min(ret_origen, tope_15)
        origen_exceso = max(ret_origen - tope_15, 0.0)

        total_bruto += bruto
        total_retencion_destino += ret_destino
        total_origen_hasta15 += origen_hasta15
        total_origen_exceso += origen_exceso
        if origen_exceso > 0:
            exceso_por_grupo[_grupo_origen(valor.zona, valor.mercado)] += origen_exceso

        listado_dividendos.append(
            {
                "fecha_mostrar": op.fecha.strftime("%d/%m/%Y"),
                "_fecha": op.fecha.isoformat(),
                "cartera": mapa_cartera.get(op.id_cartera, ""),
                "ticker": valor.ticker,
                "empresa": valor.empresa,
                "tipo": "Dividendo" if es_dividendo else "Venta de derechos",
                "importe": round(bruto, 2),
                "importe_mostrar": formatear_eur(bruto),
                "retencion_destino": round(ret_destino, 2),
                "retencion_destino_mostrar": formatear_eur(ret_destino),
                "retencion_origen_hasta15": round(origen_hasta15, 2),
                "retencion_origen_hasta15_mostrar": formatear_eur(origen_hasta15),
                "retencion_origen_exceso": round(origen_exceso, 2),
                "retencion_origen_exceso_mostrar": formatear_eur(origen_exceso),
            }
        )
    listado_dividendos.sort(key=lambda f: f["_fecha"])
    for f in listado_dividendos:
        del f["_fecha"]

    exceso_origen_por_zona = [
        {"zona": zona, "importe": round(importe, 2), "importe_mostrar": formatear_eur(importe)}
        for zona, importe in sorted(exceso_por_grupo.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # --- 2) Ventas: plusvalía por lotes FIFO -------------------------------
    # Hace falta reconstruir la posición COMPLETA de cada valor+cartera
    # desde el principio (no solo las operaciones del año) para que el
    # coste de los lotes FIFO que consuma una venta de este año sea el
    # correcto -- igual que en cartera_db.obtener_tenencias / valor_db.
    posiciones: dict[tuple[int, int], PosicionFIFO] = {}
    listado_ventas = []
    total_importe_venta = 0.0
    total_coste_venta = 0.0

    operaciones_ordenadas = sorted(
        operaciones_todas,
        key=lambda t: (t[0].fecha, _PRIORIDAD_MISMO_DIA.get(t[0].tipo_operacion, 1)),
    )
    for op, valor in operaciones_ordenadas:
        clave = (op.id_cartera, op.id_valor)
        posicion = posiciones.setdefault(clave, PosicionFIFO())

        if op.tipo_operacion == "Venta":
            coste_vendido = posicion.vender(op.num_titulos)
            if op.fecha.year == anio:
                plusvalia = op.importe - coste_vendido
                total_importe_venta += op.importe
                total_coste_venta += coste_vendido
                listado_ventas.append(
                    {
                        "fecha_mostrar": op.fecha.strftime("%d/%m/%Y"),
                        "_fecha": op.fecha.isoformat(),
                        "cartera": mapa_cartera.get(op.id_cartera, ""),
                        "ticker": valor.ticker,
                        "empresa": valor.empresa,
                        "num_titulos": op.num_titulos,
                        "num_titulos_mostrar": formatear_titulos(op.num_titulos),
                        "importe_venta": round(op.importe, 2),
                        "importe_venta_mostrar": formatear_eur(op.importe),
                        "coste": round(coste_vendido, 2),
                        "coste_mostrar": formatear_eur(coste_vendido),
                        "plusvalia": round(plusvalia, 2),
                        "plusvalia_mostrar": formatear_eur(plusvalia),
                        "color_plusvalia": gain_loss_color(plusvalia),
                        "retencion_mostrar": "",
                    }
                )
        elif op.tipo_operacion == "Prima":
            posicion.aplicar_prima(op.importe)
        elif op.tipo_operacion in ("Split", "Contrasplit"):
            # Split/Contrasplit no genera plusvalía (solo reescala los
            # lotes), SALVO cuando el ratio deja una fracción de título
            # que el bróker pagó en efectivo (tipo_ajuste_fraccion ==
            # "Venta") -- eso sí es una transmisión real de esa
            # fracción, y entra aquí como una "venta" más, con su
            # propia plusvalía FIFO. Ojo: la retención que pueda llevar
            # esta fracción (ver models.Operacion.retencion_origen/
            # retencion_destino) se muestra en su fila de este listado
            # de ventas, y SÍ suma al total de plusvalía de ventas (es
            # una ganancia/pérdida patrimonial más), pero A PROPÓSITO
            # no se mezcla con los totales de retención de la sección
            # de dividendos de arriba: en el IRPF, la retención de una
            # ganancia patrimonial (transmisión) va en una casilla
            # distinta a la de los rendimientos del capital mobiliario
            # (dividendos) -- se queda solo como dato informativo en su
            # fila, para que Gabriel la ubique él mismo en la casilla
            # correcta de la declaración.
            fraccion, coste_fraccion = aplicar_split_y_fraccion(posicion, op)
            if (
                op.tipo_ajuste_fraccion == "Venta"
                and fraccion > 1e-6
                and op.fecha.year == anio
            ):
                plusvalia = op.importe - coste_fraccion
                total_importe_venta += op.importe
                total_coste_venta += coste_fraccion
                ret_total = (op.retencion_origen or 0.0) + (op.retencion_destino or 0.0)
                listado_ventas.append(
                    {
                        "fecha_mostrar": op.fecha.strftime("%d/%m/%Y"),
                        "_fecha": op.fecha.isoformat(),
                        "cartera": mapa_cartera.get(op.id_cartera, ""),
                        "ticker": valor.ticker,
                        "empresa": (
                            f"{valor.empresa} (fracción de {op.tipo_operacion.lower()})"
                        ),
                        "num_titulos": fraccion,
                        "num_titulos_mostrar": formatear_titulos(fraccion),
                        "importe_venta": round(op.importe, 2),
                        "importe_venta_mostrar": formatear_eur(op.importe),
                        "coste": round(coste_fraccion, 2),
                        "coste_mostrar": formatear_eur(coste_fraccion),
                        "plusvalia": round(plusvalia, 2),
                        "plusvalia_mostrar": formatear_eur(plusvalia),
                        "color_plusvalia": gain_loss_color(plusvalia),
                        "retencion_mostrar": (
                            formatear_eur(ret_total) if ret_total else ""
                        ),
                    }
                )
        elif op.tipo_operacion == "Spinoff":
            # A diferencia de Split/Contrasplit, Spinoff nunca genera
            # aquí una plusvalía por sí mismo: si el ratio de títulos
            # deja una fracción que se cobró en efectivo, esa fracción
            # se registra como una Venta NORMAL aparte (ver
            # states/alta_operacion_form.py._guardar_spinoff), que ya
            # cae en la rama de arriba con todo el tratamiento fiscal
            # correcto -- no hace falta duplicarlo aquí.
            aplicar_spinoff(posicion, op)
        elif _aporta_titulos(op):
            coste_unitario = (
                (op.importe / op.num_titulos) if _aporta_coste(op) and op.num_titulos else 0.0
            )
            posicion.comprar(op.num_titulos, coste_unitario)

    listado_ventas.sort(key=lambda f: f["_fecha"])
    for f in listado_ventas:
        del f["_fecha"]

    total_plusvalia_ventas = total_importe_venta - total_coste_venta

    return {
        "listado_dividendos": listado_dividendos,
        "listado_ventas": listado_ventas,
        "exceso_origen_por_zona": exceso_origen_por_zona,
        "total_bruto_dividendos": round(total_bruto, 2),
        "total_bruto_dividendos_mostrar": formatear_eur(total_bruto),
        "total_retencion_destino": round(total_retencion_destino, 2),
        "total_retencion_destino_mostrar": formatear_eur(total_retencion_destino),
        "total_retencion_origen_hasta15": round(total_origen_hasta15, 2),
        "total_retencion_origen_hasta15_mostrar": formatear_eur(total_origen_hasta15),
        "total_retencion_origen_exceso": round(total_origen_exceso, 2),
        "total_retencion_origen_exceso_mostrar": formatear_eur(total_origen_exceso),
        "total_importe_venta": round(total_importe_venta, 2),
        "total_importe_venta_mostrar": formatear_eur(total_importe_venta),
        "total_coste_venta": round(total_coste_venta, 2),
        "total_coste_venta_mostrar": formatear_eur(total_coste_venta),
        "total_plusvalia_ventas": round(total_plusvalia_ventas, 2),
        "total_plusvalia_ventas_mostrar": formatear_eur(total_plusvalia_ventas),
        "color_total_plusvalia_ventas": gain_loss_color(total_plusvalia_ventas),
    }

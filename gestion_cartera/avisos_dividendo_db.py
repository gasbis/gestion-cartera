"""Avisos de bajada del dividendo por acción (DPA), para la página de
Inicio: valores de la cartera cuyo DPA del último año natural completo
ha bajado más de un `UMBRAL_BAJADA` respecto al año anterior.

Cómo se calcula el DPA de un año: suma, pago a pago, de lo cobrado por
cada título que se tenía en ese momento --
  - Dividendo: importe / títulos de esa operación.
  - Script: (dinero cobrado por vender derechos + valoración neta de los
    títulos recibidos, ver dividendos_scrip.py) / títulos que se tenían
    justo antes del scrip.
Así un valor que pasa de pagar en efectivo a pagar en scrip (o al revés)
no da un falso aviso, siempre que el scrip esté valorado.

Para evitar falsos avisos:
  - Solo se comparan valores que se tenían ya el 1 de enero del primero
    de los dos años y se siguen teniendo hoy (con una compra a mitad de
    año se cobran menos pagos, pero eso no es una bajada del dividendo).
  - Si el número de pagos cambia entre un año y otro (un pago que se
    retrasa de diciembre a enero, por ejemplo) se avisa igualmente, pero
    con una nota para revisarlo.
  - En valores que no cotizan en euros, el DPA en euros varía también con
    el tipo de cambio: se indica en la nota.
"""

from collections import defaultdict
from datetime import date

import reflex as rx
import sqlmodel

from gestion_cartera.cartera_db import (
    _PRIORIDAD_MISMO_DIA,
    PosicionFIFO,
    _aporta_coste,
    _aporta_titulos,
    aplicar_split_y_fraccion,
    aplicar_spinoff,
)
from gestion_cartera.dividendos_scrip import valor_neto_scrip
from gestion_cartera.format_utils import formatear_numero, formatear_pct
from gestion_cartera.models import Operacion, Valor

# Bajada mínima del DPA (en tanto por uno) para avisar. Con menos, la
# simple variación del tipo de cambio en valores en dólares o libras ya
# daría avisos casi todos los años.
UMBRAL_BAJADA = 0.10


def obtener_avisos_dividendo(id_cartera: int, hoy: date | None = None) -> dict:
    """{"anio": 2025, "anio_anterior": 2024, "comparados": 23,
    "avisos": [{ticker, empresa, dpa_anterior_mostrar, dpa_mostrar,
    variacion_mostrar, nota}, ...]} -- avisos ordenados de mayor a menor
    bajada."""
    hoy = hoy or date.today()
    anio = hoy.year - 1
    anio_anterior = anio - 1
    inicio_periodo = date(anio_anterior, 1, 1)

    with rx.session() as session:
        operaciones = session.exec(
            sqlmodel.select(Operacion).where(Operacion.id_cartera == id_cartera)
        ).all()
        valores = {v.id: v for v in session.exec(sqlmodel.select(Valor)).all()}

    por_valor: dict[int, list[Operacion]] = defaultdict(list)
    for op in operaciones:
        por_valor[op.id_valor].append(op)

    avisos = []
    comparados = 0
    for id_valor, ops in por_valor.items():
        ops.sort(key=lambda op: (op.fecha, _PRIORIDAD_MISMO_DIA.get(op.tipo_operacion, 1)))
        posicion = PosicionFIFO()
        titulos_al_inicio = None
        dpa: dict[int, float] = defaultdict(float)
        pagos: dict[int, int] = defaultdict(int)
        scrip_sin_valorar = False

        for op in ops:
            if titulos_al_inicio is None and op.fecha >= inicio_periodo:
                titulos_al_inicio = posicion.titulos
            titulos_antes = posicion.titulos

            # Cobros por título (antes de mover la posición).
            if op.fecha.year in (anio_anterior, anio):
                if op.tipo_operacion == "Dividendo":
                    base = op.num_titulos or titulos_antes
                    if base > 0:
                        dpa[op.fecha.year] += op.importe / base
                        pagos[op.fecha.year] += 1
                elif op.tipo_operacion == "Script" and titulos_antes > 0:
                    cobrado = op.importe if op.tipo_derecho_script == "Venta" else 0.0
                    dpa[op.fecha.year] += (cobrado + valor_neto_scrip(op)) / titulos_antes
                    pagos[op.fecha.year] += 1
                    if op.valoracion_script_eur is None:
                        scrip_sin_valorar = True

            # Efecto sobre la posición (mismo motor que cartera_db).
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

        if titulos_al_inicio is None:
            titulos_al_inicio = posicion.titulos
        # Hay que tenerlo desde antes del periodo, seguir teniéndolo, y
        # que pagara algo el primer año para tener con qué comparar.
        if titulos_al_inicio <= 1e-9 or posicion.titulos <= 1e-9 or dpa[anio_anterior] <= 0:
            continue
        comparados += 1

        variacion = dpa[anio] / dpa[anio_anterior] - 1
        if variacion > -UMBRAL_BAJADA:
            continue

        valor = valores.get(id_valor)
        notas = []
        if pagos[anio] == 0:
            notas.append(f"Sin ningún pago en {anio}.")
        elif pagos[anio] != pagos[anio_anterior]:
            notas.append(
                f"Pagos: {pagos[anio_anterior]} en {anio_anterior} y {pagos[anio]} en {anio}; "
                "puede ser un cambio de calendario."
            )
        if valor is not None and valor.moneda.upper() != "EUR":
            notas.append(f"Cotiza en {valor.moneda.upper()}: incluye el efecto del tipo de cambio.")
        if scrip_sin_valorar:
            notas.append("Hay scrips sin valorar en estos años.")

        avisos.append(
            {
                "ticker": valor.ticker if valor else "",
                "empresa": valor.empresa if valor else "",
                "variacion": variacion,
                "dpa_anterior_mostrar": f"{formatear_numero(dpa[anio_anterior], 4)} €",
                "dpa_mostrar": f"{formatear_numero(dpa[anio], 4)} €",
                "variacion_mostrar": formatear_pct(round(variacion * 100, 1), 1),
                "nota": " ".join(notas),
            }
        )

    avisos.sort(key=lambda a: a["variacion"])
    for a in avisos:
        del a["variacion"]
    return {
        "anio": anio,
        "anio_anterior": anio_anterior,
        "comparados": comparados,
        "avisos": avisos,
    }

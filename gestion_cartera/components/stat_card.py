"""Tarjeta de cifra clave (resúmenes de Inicio/Cartera/valor_detalle).

Fase 2 del rediseño visual: antes cada página definía su propia versión
de esta tarjeta (mismo patrón `rx.card(rx.flex(rx.text(...),
rx.heading(...)))` copiado tres veces, con ligeras diferencias de
tamaño), y todas pesaban igual en pantalla -- ninguna destacaba sobre
las demás aunque unas fueran mucho más relevantes que otras (Plusvalía,
T.I.R., Saldo) que las puramente informativas (Nº de valores).

Este componente unifica las tres y añade jerarquía:
  - El número es más grande y en negrita (antes `size="5"`/`"6"` sin
    peso explícito -- ahora `size="7"`, `weight="bold"`).
  - Las tarjetas con significado financiero (`value_color` != None,
    es decir ganancia/pérdida) llevan además una franja de color a la
    izquierda del mismo color semántico, para que se distingan de un
    vistazo de las puramente descriptivas (Nº de valores, etc.) sin
    tener que leer el número.
"""

import reflex as rx


def stat_card(
    title: str,
    value,
    description: str | None = None,
    secondary=None,
    value_color=None,
) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.text(title, size="2", color_scheme="gray", weight="medium"),
            rx.heading(value, size="7", weight="bold", color=value_color),
            *([rx.text(secondary, size="2", weight="medium", color=value_color)] if secondary is not None else []),
            # spacer + description al final: en una fila de varias
            # tarjetas (ver summary_section en pages/index.py) todas se
            # estiran a la altura de la más alta -- solo las que llevan
            # `secondary` (Saldo, T.I.R.) son más altas -- así que sin
            # esto, la description quedaba a distinta altura según la
            # tarjeta tuviera o no esa línea de más. Con el spacer
            # queda siempre pegada abajo.
            rx.spacer(),
            *([rx.text(description, size="1", color_scheme="gray")] if description is not None else []),
            direction="column",
            spacing="2",
            height="100%",
        ),
        # Franja de acento a la izquierda solo en las tarjetas con
        # significado financiero (ganancia/pérdida/neutro) -- las
        # meramente informativas (p.ej. "Nº de valores") no lo llevan,
        # así la franja funciona como señal, no como decoración fija.
        border_left=f"3px solid {value_color}" if value_color is not None else None,
        width="100%",
        height="100%",
    )

"""Barra de cartera: selector Largo/Corto Plazo, a quién pertenece (y
desde cuándo) y fecha de la última operación. Vive dentro del header
(components/header.py), así que aparece en todas las páginas.

Al cambiar de cartera se recarga siempre el propio header
(HeaderState); cada página añade además su propia recarga a través de
`extra_on_change` (ver header()), para que sus datos también se
actualicen sin tener que cambiar de página y volver.
"""

import reflex as rx

from gestion_cartera.states.header_state import HeaderState
from gestion_cartera.states.portfolio_state import PortfolioState
from gestion_cartera.styles import LINK_COLOR, SPACE_MD, SPACE_SM


def control_bar(extra_on_change: list | None = None) -> rx.Component:
    return rx.hstack(
        rx.hstack(
            # Solo hay dos carteras (Largo Plazo / Corto Plazo), así que
            # un interruptor es más directo que un desplegable -- a
            # petición expresa, en vez de "Cartera: Largo Plazo ▾" ahora
            # es "Cartera de largo plazo [interruptor]", con el propio
            # texto cambiando según la posición.
            rx.text(
                rx.cond(
                    PortfolioState.es_largo_plazo,
                    "Cartera de largo plazo",
                    "Cartera de corto plazo",
                ),
                weight="medium",
                size="2",
            ),
            rx.switch(
                checked=PortfolioState.es_largo_plazo,
                on_change=[
                    PortfolioState.set_es_largo_plazo,
                    HeaderState.cargar_datos,
                    *(extra_on_change or []),
                ],
                size="2",
            ),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.cond(
            HeaderState.nombre_usuario != "",
            rx.hstack(
                rx.text("Propiedad de", size="2", color_scheme="gray"),
                rx.text(
                    HeaderState.nombre_usuario,
                    size="2",
                    weight="medium",
                    color=LINK_COLOR,
                ),
                rx.cond(
                    HeaderState.fecha_inicio_mostrar != "",
                    rx.text(
                        f"· iniciada en {HeaderState.fecha_inicio_mostrar}",
                        size="2",
                        color_scheme="gray",
                    ),
                ),
                spacing="1",
                align="center",
            ),
        ),
        rx.spacer(),
        rx.text(
            f"Última operación: {HeaderState.fecha_ultima_operacion_mostrar}",
            size="2",
            color_scheme="gray",
        ),
        width="100%",
        padding_x=SPACE_MD,
        # Menos separación por arriba en los formatos que usan el menú
        # hamburguesa (por debajo de "md"), a juego con el recorte del
        # padding inferior de la fila de arriba (ver header.py) -- para
        # que ambas filas queden más juntas en móvil.
        padding_top=rx.breakpoints(initial="0.25em", md=SPACE_SM),
        padding_bottom=SPACE_SM,
        border_bottom="1px solid var(--app-separator)",
        align="center",
        wrap="wrap",
    )

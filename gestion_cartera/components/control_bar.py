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
            rx.text("Cartera:", weight="medium", size="2"),
            rx.select(
                PortfolioState.PORTFOLIOS,
                value=PortfolioState.selected_portfolio,
                on_change=[
                    PortfolioState.set_portfolio,
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
        padding_y=SPACE_SM,
        border_bottom="1px solid var(--gray-a5)",
        align="center",
        wrap="wrap",
    )

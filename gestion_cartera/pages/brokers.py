"""Página BROKERS: alta de brokers nuevos y control de existencias por
bróker (para cuadrar contra el extracto real), agregando las dos
carteras.
"""

import reflex as rx

from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.header import header
from gestion_cartera.components.page_title import page_title
from gestion_cartera.components.scroll_x import scroll_x
from gestion_cartera.states.brokers_state import BrokersState
from gestion_cartera.styles import SPACE_MD, SPACE_SM


def fila_broker(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["nombre"]),
        rx.table.cell(
            rx.button(
                "Ver existencias",
                size="1",
                variant="soft",
                on_click=BrokersState.ver_existencias(item["id"]),
            )
        ),
    )


def fila_existencia(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["ticker"], weight="medium"),
        rx.table.cell(item["mercado"]),
        rx.table.cell(item["empresa"]),
        rx.table.cell(item["num_titulos_mostrar"]),
    )


def alta_broker_form() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading("Dar de alta un bróker nuevo", size="3"),
            rx.text(
                "Los brokers no se pueden eliminar: forman parte del histórico "
                "de operaciones.",
                size="1",
                color_scheme="gray",
            ),
            rx.hstack(
                rx.input(
                    placeholder="Nombre del bróker",
                    value=BrokersState.nombre_nuevo_broker,
                    on_change=BrokersState.set_nombre_nuevo_broker,
                    width="100%",
                ),
                rx.button("Dar de alta", on_click=BrokersState.dar_alta_broker),
                spacing="3",
                width="100%",
                wrap="wrap",
            ),
            rx.cond(
                BrokersState.alta_error != "",
                rx.callout(BrokersState.alta_error, color_scheme="red", size="1"),
            ),
            rx.cond(
                BrokersState.alta_ok,
                rx.callout("Bróker dado de alta correctamente.", color_scheme="green", size="1"),
            ),
            direction="column",
            spacing="3",
        ),
        width="100%",
    )


def existencias_section() -> rx.Component:
    return rx.cond(
        BrokersState.broker_seleccionado_id > 0,
        rx.card(
            rx.flex(
                rx.heading(
                    "Existencias en " + BrokersState.broker_seleccionado_nombre,
                    size="3",
                ),
                rx.text(
                    "Suma de las dos carteras (Largo Plazo + Corto Plazo): así se "
                    "compara directamente contra el extracto real del bróker.",
                    size="1",
                    color_scheme="gray",
                ),
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Ticker"),
                                rx.table.column_header_cell("Mercado"),
                                rx.table.column_header_cell("Empresa"),
                                rx.table.column_header_cell("Nº títulos"),
                            )
                        ),
                        rx.table.body(rx.foreach(BrokersState.existencias, fila_existencia)),
                        width="100%",
                    ),
                ),
                rx.cond(
                    BrokersState.existencias.length() == 0,
                    rx.text(
                        "No hay títulos depositados en este bróker.",
                        color_scheme="gray",
                        size="2",
                        padding_y=SPACE_SM,
                    ),
                ),
                direction="column",
                spacing="3",
            ),
            width="100%",
        ),
    )


def pagina_brokers() -> rx.Component:
    return rx.container(
        header(),
        rx.flex(
            page_title(
                "Brókers",
                "Brokers dados de alta y control de existencias por bróker.",
            ),
            alta_broker_form(),
            rx.card(
                rx.flex(
                    rx.heading("Brókers", size="3"),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Nombre"),
                                rx.table.column_header_cell(""),
                            )
                        ),
                        rx.table.body(rx.foreach(BrokersState.brokers, fila_broker)),
                        width="100%",
                    ),
                    direction="column",
                    spacing="3",
                ),
                width="100%",
            ),
            existencias_section(),
            direction="column",
            spacing="4",
            padding="1em",
        ),
        size="4",
    )


def brokers() -> rx.Component:
    return requiere_login(pagina_brokers())

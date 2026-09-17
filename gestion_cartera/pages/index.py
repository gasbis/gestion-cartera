import reflex as rx
from gestion_cartera.components.header import header
from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.styles import (
    SPACE_MD,
    SPACE_SM,
    gain_loss_color,
)

from rxconfig import config


class PortfolioState(rx.State):
    """Estado de selección de año y cartera en la página principal.

    Se mantiene como State (y no como valor local) porque más adelante
    este año/cartera seleccionados serán los que filtren los datos que
    se traen de la base de datos para el usuario logueado.
    """

    PORTFOLIOS: list[str] = ["Largo Plazo", "Corto Plazo"]

    selected_portfolio: str = "Largo Plazo"

    def set_portfolio(self, portfolio: str):
        self.selected_portfolio = portfolio


def control_bar() -> rx.Component:
    """Barra compacta de selección de cartera (sin selector de año: no
    tiene sentido en la página principal, como indicaste)."""
    return rx.hstack(
        rx.hstack(
            rx.text("Cartera:", weight="medium", size="2"),
            rx.select(
                PortfolioState.PORTFOLIOS,
                value=PortfolioState.selected_portfolio,
                on_change=PortfolioState.set_portfolio,
                size="2",
            ),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.text(
            "Última operación: 27/08/2026",
            size="2",
            color_scheme="gray",
        ),
        width="100%",
        padding_x=SPACE_MD,
        padding_y=SPACE_SM,
        border_bottom="1px solid var(--gray-a5)",
        align="center",
    )


def summary_card(
    title: str, value: str, description: str, value_color: str | None = None
) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.text(title, size="2", color_scheme="gray", weight="medium"),
            rx.heading(value, size="6", color=value_color),
            rx.text(description, size="1", color_scheme="gray"),
            direction="column",
            spacing="2",
        ),
        size="2",
        width="100%",
    )


def summary_section() -> rx.Component:
    # Cifras de ejemplo: cuando vengan de datos reales, el color se deriva
    # con gain_loss_color(valor_numerico) en vez de fijarlo a mano.
    saldo_valor = 234546.00
    tir_valor = 14.3

    return rx.grid(
        summary_card(
            "Valor de compra", "234.546,00 €", "Suma de las compras-ventas."
        ),
        summary_card(
            "Valor actual",
            "234.546,00 €",
            "Valoración de la cartera con la cotización actual.",
        ),
        summary_card(
            "Saldo",
            "234.546,00 € · 52,3%",
            "Diferencia entre el valor de compra y el valor actual.",
            value_color=gain_loss_color(saldo_valor),
        ),
        summary_card(
            "T.I.R.",
            "14,3% / 4,5%",
            "Rentabilidad anual con/sin revalorización.",
            value_color=gain_loss_color(tir_valor),
        ),
        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
        spacing="4",
        width="100%",
    )


def table_five(title: str) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading(title, size="3"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Ticker"),
                        rx.table.column_header_cell("Nombre"),
                        rx.table.column_header_cell("%"),
                    ),
                ),
                rx.table.body(
                    rx.table.row(
                        rx.table.row_header_cell("ELE"),
                        rx.table.cell("Endesa"),
                        rx.table.cell("10%"),
                    ),
                    rx.table.row(
                        rx.table.row_header_cell("LDA"),
                        rx.table.cell("Linea Directa"),
                        rx.table.cell("15%"),
                    ),
                    rx.table.row(
                        rx.table.row_header_cell("MICC"),
                        rx.table.cell("Compañía de helados Magnum"),
                        rx.table.cell("20%"),
                    ),
                    rx.table.row(
                        rx.table.row_header_cell("SAN"),
                        rx.table.cell("Banco Santander"),
                        rx.table.cell("10%"),
                    ),
                    rx.table.row(
                        rx.table.row_header_cell("UNA"),
                        rx.table.cell("Unilever"),
                        rx.table.cell("15%"),
                    ),
                ),
                size="1",
            ),
            direction="column",
            spacing="2",
        ),
        width="100%",
    )


def tables_section() -> rx.Component:
    return rx.grid(
        table_five("Mejores revalorizaciones"),
        table_five("Peores revalorizaciones"),
        table_five("Mejor YOC año anterior"),
        table_five("Peor YOC año anterior"),
        columns=rx.breakpoints(initial="1", md="2"),
        spacing="4",
        width="100%",
    )


data = [
    {"name": "2017", "uv": 403.03},
    {"name": "2018", "uv": 1570.37},
    {"name": "2019", "uv": 1747.10},
    {"name": "2020", "uv": 1984.00},
    {"name": "2021", "uv": 2525.75},
    {"name": "2022", "uv": 4761.97},
    {"name": "2023", "uv": 5517.65},
    {"name": "2024", "uv": 6528.89},
    {"name": "2025", "uv": 6350.55},
    {"name": "2026", "uv": 5273.37},
]


def bar_simple():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="uv",
            # Ligado al acento del tema (azul): cambiar accent_color en
            # app.py cambia este gráfico también, sin tocar este archivo.
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        rx.recharts.graphing_tooltip(),
        data=data,
        width="100%",
        height=250,
    )


def chart_section(title: str) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading(title, size="3"),
            bar_simple(),
            direction="column",
            spacing="2",
        ),
        width="100%",
    )


zona_compra = [
    {"name": "ESP", "value": 57.2},
    {"name": "EURO", "value": 11.9},
    {"name": "USA", "value": 26.2},
    {"name": "UK", "value": 4.8},
]

zona_actual = [
    {"name": "ESP", "value": 72.0},
    {"name": "EURO", "value": 6.5},
    {"name": "USA", "value": 18.1},
    {"name": "UK", "value": 3.5},
]

sector_compra = [
    {"name": "DEFENSIVO", "value": 43.8},
    {"name": "CICLICO", "value": 24.6},
    {"name": "SENSIBLE", "value": 31.6},
]

sector_actual = [
    {"name": "DEFENSIVO", "value": 28.8},
    {"name": "CICLICO", "value": 35.8},
    {"name": "SENSIBLE", "value": 35.5},
]

colors1 = ["#EC503C", "#C8E644", "#9EF755", "#46EF92"]
colors2 = ["#EFF163", "#5CF6BB", "#46E4EF"]


def pie_double(data01: list, data02: list, colors: list):
    color_palette = rx.Var.create(colors)

    return rx.recharts.pie_chart(
        # Gráfico exterior (Donut) = valor de compra
        rx.recharts.pie(
            rx.foreach(
                data01,
                lambda item, index: rx.recharts.cell(
                    fill=color_palette[index % len(colors)],
                ),
            ),
            data=data01,
            data_key="value",
            name_key="name",
            inner_radius="60%",
            outer_radius="80%",
            padding_angle=5,
        ),
        # Gráfico interior (Pastel central) = valor actual
        rx.recharts.pie(
            rx.foreach(
                data02,
                lambda item, index: rx.recharts.cell(
                    fill=color_palette[index % len(colors)],
                ),
            ),
            data=data02,
            data_key="value",
            name_key="name",
            outer_radius="50%",
        ),
        rx.recharts.graphing_tooltip(),
        width="100%",
        height=300,
    )


def pie_section(title: str, data01: list, data02: list, colors: list) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading(title, size="3"),
            pie_double(data01, data02, colors),
            rx.text(
                "Donut = valor de compra · Tarta = valor actual",
                size="1",
                color_scheme="gray",
            ),
            direction="column",
            spacing="2",
        ),
        width="100%",
    )


def index() -> rx.Component:
    return requiere_login(
        rx.container(
            header(),
            rx.color_mode.button(position="top-right"),
            control_bar(),
            rx.stack(
                summary_section(),
                tables_section(),
                chart_section("Dividendos"),
                rx.grid(
                    pie_section("Zonas", zona_compra, zona_actual, colors1),
                    pie_section("Sectores", sector_compra, sector_actual, colors2),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="4",
                    width="100%",
                ),
                direction="column",
                spacing="6",
                width="100%",
                padding=SPACE_MD,
            ),
            padding_y="0",
            size="4",
        )
    )
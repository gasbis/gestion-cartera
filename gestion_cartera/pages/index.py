import reflex as rx
from gestion_cartera.components.header import header
from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.page_title import page_title
from gestion_cartera.states.index_state import ResumenGeneralState
from gestion_cartera.styles import SPACE_MD

from rxconfig import config

# El estado de selección de cartera (PortfolioState) y la barra que lo
# muestra (control_bar) viven ahora en states/portfolio_state.py y
# components/control_bar.py respectivamente: el selector forma parte
# del header y se ve en todas las páginas, no solo en esta.


def summary_card(
    title: str, value, description: str, value_color=None, secondary=None
) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.text(title, size="2", color_scheme="gray", weight="medium"),
            rx.heading(value, size="6", color=value_color),
            *([rx.text(secondary, size="2", weight="medium", color=value_color)] if secondary is not None else []),
            rx.text(description, size="1", color_scheme="gray"),
            direction="column",
            spacing="2",
        ),
        size="2",
        width="100%",
    )


def summary_section() -> rx.Component:
    r = ResumenGeneralState.resumen
    return rx.grid(
        summary_card(
            "Valor de compra", r["valor_compra_mostrar"], "Suma de las compras-ventas."
        ),
        summary_card(
            "Valor actual",
            r["valor_mercado_mostrar"],
            "Valoración de la cartera con la cotización actual.",
        ),
        summary_card(
            "Saldo",
            r["saldo_eur_mostrar"],
            "Diferencia entre el valor de compra y el valor actual.",
            value_color=r["color_saldo"],
            secondary=r["saldo_pct_mostrar"],
        ),
        summary_card(
            "T.I.R.",
            r["tir_con_mostrar"],
            "Rentabilidad anual con / sin revalorización.",
            value_color=r["color_tir"],
            secondary=r["tir_sin_mostrar"],
        ),
        summary_card(
            "Nº de valores",
            r["numero_valores"],
            "Valores con al menos un título en esta cartera.",
        ),
        columns=rx.breakpoints(initial="1", sm="2", lg="5"),
        spacing="4",
        width="100%",
    )


def fila_top_valor(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(item["ticker"]),
        rx.table.cell(item["empresa"]),
        rx.table.cell(item["valor_mostrar"], color=item["color"], weight="medium"),
    )


def table_five(title: str, items) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading(title, size="3"),
            rx.cond(
                items.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Ticker"),
                            rx.table.column_header_cell("Nombre"),
                            rx.table.column_header_cell("%"),
                        ),
                    ),
                    rx.table.body(rx.foreach(items, fila_top_valor)),
                    size="1",
                ),
                rx.text("Sin datos todavía.", size="2", color_scheme="gray"),
            ),
            direction="column",
            spacing="2",
        ),
        width="100%",
    )


def tables_section() -> rx.Component:
    return rx.grid(
        table_five("Mejores revalorizaciones", ResumenGeneralState.top_valores["mejor_revalorizacion"]),
        table_five("Peores revalorizaciones", ResumenGeneralState.top_valores["peor_revalorizacion"]),
        table_five("Mejor YOC año anterior", ResumenGeneralState.top_valores["mejor_yoc"]),
        table_five("Peor YOC año anterior", ResumenGeneralState.top_valores["peor_yoc"]),
        # sm (768px) y no md (992px): así una tablet en vertical ya
        # mantiene las dos tablas por renglón en vez de apilarlas.
        columns=rx.breakpoints(initial="1", sm="2"),
        spacing="4",
        width="100%",
    )


def bar_simple(data) -> rx.Component:
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            # Etiqueta con la cifra ya formateada encima de cada barra: el
            # dato que dibuja la altura ("uv", numérico) y el que se
            # muestra ("uv_mostrar", ya formateado en €) son dos campos
            # distintos del mismo registro, así no hace falta pasar el
            # ratón por encima para ver el valor.
            rx.recharts.label_list(
                data_key="uv_mostrar", position="top", fill=rx.color("gray", 11)
            ),
            data_key="uv",
            # Ligado al acento del tema (azul): cambiar accent_color en
            # app.py cambia este gráfico también, sin tocar este archivo.
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
            radius=[4, 4, 0, 0],
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(axis_line=False, tick_line=False),
        rx.recharts.cartesian_grid(horizontal=True, vertical=False, stroke=rx.color("gray", 4)),
        data=data,
        margin={"top": 20},
        width="100%",
        height=250,
    )


def chart_section(title: str, data, total: rx.Var | None = None) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.flex(
                rx.heading(title, size="3"),
                rx.spacer(),
                *(
                    [rx.text(total, size="4", weight="bold", color=rx.color("accent", 11))]
                    if total is not None
                    else []
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                data.length() > 0,
                bar_simple(data),
                rx.text("Sin dividendos registrados todavía.", size="2", color_scheme="gray"),
            ),
            direction="column",
            spacing="2",
        ),
        width="100%",
    )


def distribucion_chart(data) -> rx.Component:
    """Barras horizontales agrupadas: dos barras por zona/sector (valor
    de compra vs. valor actual), mismo tono en dos intensidades (antes /
    después), con el % ya escrito en la propia barra -- así se compara
    de un vistazo cómo ha cambiado el peso de cada grupo sin tener que
    pasar el ratón por encima ni comparar ángulos de un donut."""
    altura = data.length() * 70 + 20
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key="compra_pct_mostrar", position="right", fill=rx.color("gray", 11)
            ),
            data_key="compra_pct",
            name="Valor de compra",
            fill=rx.color("accent", 5),
            radius=[0, 4, 4, 0],
        ),
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key="actual_pct_mostrar", position="right", fill=rx.color("gray", 11)
            ),
            data_key="actual_pct",
            name="Valor actual",
            fill=rx.color("accent", 9),
            radius=[0, 4, 4, 0],
        ),
        rx.recharts.x_axis(type_="number", hide=True),
        rx.recharts.y_axis(data_key="name", type_="category", axis_line=False, tick_line=False, width=70),
        rx.recharts.legend(),
        data=data,
        layout="vertical",
        margin={"right": 40},
        width="100%",
        height=altura,
    )


def distribucion_section(title: str, data) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading(title, size="3"),
            rx.cond(
                data.length() > 0,
                distribucion_chart(data),
                rx.text("Sin datos todavía.", size="2", color_scheme="gray"),
            ),
            direction="column",
            spacing="2",
        ),
        width="100%",
    )


def index() -> rx.Component:
    return requiere_login(
        rx.container(
            header(extra_on_portfolio_change=[ResumenGeneralState.cargar_datos]),
            rx.stack(
                page_title("Inicio", "Resumen general de tu cartera de inversiones."),
                summary_section(),
                tables_section(),
                chart_section(
                    "Dividendos",
                    ResumenGeneralState.dividendos_por_anio,
                    total=ResumenGeneralState.dividendos_totales_mostrar,
                ),
                rx.grid(
                    distribucion_section("Zonas", ResumenGeneralState.zonas),
                    distribucion_section("Sectores", ResumenGeneralState.sectores),
                    columns=rx.breakpoints(initial="1", sm="2"),
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

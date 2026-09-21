"""Página CARTERA: listado de tenencias (una fila por valor, agregando
todos los brokers) con precio medio de compra, cotización actual (se
refresca sola al entrar, vía Twelve Data), valor de mercado, plusvalía y
peso en cartera. Con buscador y orden por columna.
"""

import reflex as rx

from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.header import header
from gestion_cartera.components.page_title import page_title
from gestion_cartera.states.cartera_state import CarteraState
from gestion_cartera.styles import (
    NEGATIVE,
    NEUTRAL,
    POSITIVE,
    SPACE_MD,
    SPACE_SM,
    STICKY_TABLE_HEADER,
)


def color_ganancia(valor: rx.Var) -> rx.Var:
    return rx.cond(valor > 0, POSITIVE, rx.cond(valor < 0, NEGATIVE, NEUTRAL))


# Padding horizontal reducido para columnas de contenido corto
# (Supersector, Zona, Nº títulos): así la tabla ocupa menos ancho total
# y, en pantallas anchas, cabe entera sin necesidad de scroll_x.
PADDING_ESTRECHO = "0.4em"


def columna_ordenable(label: str, campo_nombre: str, padding_x: str | None = None) -> rx.Component:
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(label, weight="medium", size="2"),
            rx.cond(
                CarteraState.orden_campo == campo_nombre,
                rx.icon(
                    tag=rx.cond(CarteraState.orden_desc, "chevron-down", "chevron-up"),
                    size=14,
                ),
            ),
            spacing="1",
            align="center",
        ),
        on_click=CarteraState.set_orden(campo_nombre),
        cursor="pointer",
        user_select="none",
        **STICKY_TABLE_HEADER,
        **({"padding_x": padding_x} if padding_x is not None else {}),
    )


def fila_tenencia(item: dict) -> rx.Component:
    # white_space="nowrap" en las celdas numéricas: sin esto, dentro de
    # la tabla con scroll horizontal (ver scroll_x más abajo), Radix
    # sigue encogiendo cada columna a lo mínimo posible y el símbolo
    # €/% se va a un segundo renglón. Con nowrap, si no cabe, la propia
    # tabla se desplaza en vez de partir la cifra.
    return rx.table.row(
        rx.table.cell(item["ticker"], weight="medium"),
        rx.table.cell(item["empresa"]),
        rx.table.cell(
            item["supersector"], size="1", color_scheme="gray", padding_x=PADDING_ESTRECHO
        ),
        rx.table.cell(item["sector"], size="1", color_scheme="gray"),
        rx.table.cell(item["zona"], padding_x=PADDING_ESTRECHO),
        rx.table.cell(
            item["num_titulos_mostrar"], white_space="nowrap", padding_x=PADDING_ESTRECHO
        ),
        rx.table.cell(item["precio_medio_mostrar"], white_space="nowrap"),
        rx.table.cell(item["cotizacion_actual_mostrar"], white_space="nowrap"),
        rx.table.cell(item["valor_mercado_mostrar"], weight="medium", white_space="nowrap"),
        rx.table.cell(
            item["plusvalia_eur_mostrar"],
            color=item["color_plusvalia"],
            white_space="nowrap",
        ),
        rx.table.cell(
            item["plusvalia_pct_mostrar"],
            color=item["color_plusvalia"],
            white_space="nowrap",
        ),
        rx.table.cell(item["yoc_anterior_mostrar"], white_space="nowrap"),
        rx.table.cell(item["peso_cartera_pct_mostrar"], white_space="nowrap"),
        on_click=rx.redirect(f"/valor/{item['id_valor']}"),
        style={"cursor": "pointer"},
        _hover={"background_color": "var(--gray-a2)"},
    )


def fila_valor_liquidado(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["ticker"], weight="medium"),
        rx.table.cell(item["empresa"]),
        rx.table.cell(item["supersector"], size="1", color_scheme="gray"),
        rx.table.cell(item["zona"]),
        rx.table.cell(item["fecha_ultima_operacion_mostrar"], white_space="nowrap"),
        rx.table.cell(item["invertido_historico_mostrar"], white_space="nowrap"),
        rx.table.cell(item["dividendos_acumulados_mostrar"], white_space="nowrap"),
        rx.table.cell(item["venta_derechos_acumulada_mostrar"], white_space="nowrap"),
        rx.table.cell(
            item["resultado_mostrar"],
            color=item["color_resultado"],
            weight="medium",
            white_space="nowrap",
        ),
        on_click=rx.redirect(f"/valor/{item['id_valor']}"),
        style={"cursor": "pointer"},
        _hover={"background_color": "var(--gray-a2)"},
    )


def tabla_valores_liquidados() -> rx.Component:
    return rx.cond(
        CarteraState.valores_liquidados.length() > 0,
        rx.flex(
            rx.heading("Valores liquidados", size="4"),
            rx.text(
                "Valores que has tenido en esta cartera pero de los que ya no posees "
                "ningún título. Pulsa una fila para ver su histórico completo.",
                size="2",
                color_scheme="gray",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Ticker", **STICKY_TABLE_HEADER),
                        rx.table.column_header_cell("Empresa", **STICKY_TABLE_HEADER),
                        rx.table.column_header_cell("Supersector", **STICKY_TABLE_HEADER),
                        rx.table.column_header_cell("Zona", **STICKY_TABLE_HEADER),
                        rx.table.column_header_cell(
                            "Última operación", **STICKY_TABLE_HEADER
                        ),
                        rx.table.column_header_cell("Invertido", **STICKY_TABLE_HEADER),
                        rx.table.column_header_cell("Dividendos", **STICKY_TABLE_HEADER),
                        rx.table.column_header_cell(
                            "Venta derechos", **STICKY_TABLE_HEADER
                        ),
                        rx.table.column_header_cell("Resultado", **STICKY_TABLE_HEADER),
                    ),
                ),
                rx.table.body(
                    rx.foreach(CarteraState.valores_liquidados, fila_valor_liquidado)
                ),
                width="100%",
                height="50vh",
                min_width="0",
            ),
            direction="column",
            spacing="3",
            width="100%",
        ),
    )


def resumen_cartera() -> rx.Component:
    return rx.grid(
        rx.card(
            rx.flex(
                rx.text("Valor de compra", size="2", color_scheme="gray", weight="medium"),
                rx.heading(CarteraState.valor_total_compra_mostrar, size="5"),
                direction="column",
                spacing="1",
            ),
        ),
        rx.card(
            rx.flex(
                rx.text("Valor actual", size="2", color_scheme="gray", weight="medium"),
                rx.heading(CarteraState.valor_total_mercado_mostrar, size="5"),
                direction="column",
                spacing="1",
            ),
        ),
        rx.card(
            rx.flex(
                rx.text("Plusvalía", size="2", color_scheme="gray", weight="medium"),
                rx.heading(
                    CarteraState.plusvalia_total_eur_mostrar,
                    size="5",
                    color=color_ganancia(CarteraState.plusvalia_total_eur),
                ),
                rx.text(
                    CarteraState.plusvalia_total_pct_mostrar,
                    size="2",
                    weight="medium",
                    color=color_ganancia(CarteraState.plusvalia_total_eur),
                ),
                direction="column",
                spacing="1",
            ),
        ),
        rx.card(
            rx.flex(
                rx.text("Nº de valores", size="2", color_scheme="gray", weight="medium"),
                rx.heading(CarteraState.numero_valores, size="5"),
                direction="column",
                spacing="1",
            ),
        ),
        rx.card(
            rx.flex(
                rx.text(
                    "Rentabilidad (TIR anual)", size="2", color_scheme="gray", weight="medium"
                ),
                rx.heading(CarteraState.tir_con_revalorizacion_mostrar, size="5"),
                rx.text(
                    f"Sin revalorización: {CarteraState.tir_sin_revalorizacion_mostrar}",
                    size="1",
                    color_scheme="gray",
                ),
                direction="column",
                spacing="1",
            ),
        ),
        columns=rx.breakpoints(initial="1", sm="2", lg="5"),
        spacing="4",
        width="100%",
    )


def pagina_cartera() -> rx.Component:
    return rx.container(
        header(extra_on_portfolio_change=[CarteraState.cargar_datos]),
        rx.flex(
            page_title(
                "Cartera",
                "Tenencias actuales de la cartera seleccionada, con cotización en vivo.",
            ),
            resumen_cartera(),
            rx.hstack(
                rx.input(
                    placeholder="Buscar por ticker, empresa, sector o zona…",
                    value=CarteraState.busqueda,
                    on_change=CarteraState.set_busqueda,
                    max_width="320px",
                    width="100%",
                ),
                rx.spacer(),
                rx.cond(
                    CarteraState.actualizando_cotizaciones,
                    rx.hstack(
                        rx.spinner(size="2"),
                        rx.text("Actualizando cotizaciones…", size="2", color_scheme="gray"),
                        spacing="2",
                        align="center",
                    ),
                ),
                width="100%",
                align="center",
                wrap="wrap",
            ),
            rx.cond(
                CarteraState.cotizaciones_error != "",
                rx.callout(CarteraState.cotizaciones_error, color_scheme="amber", size="1"),
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        columna_ordenable("Ticker", "ticker"),
                        columna_ordenable("Empresa", "empresa"),
                        columna_ordenable("Supersector", "supersector", padding_x=PADDING_ESTRECHO),
                        rx.table.column_header_cell("Sector", **STICKY_TABLE_HEADER),
                        columna_ordenable("Zona", "zona", padding_x=PADDING_ESTRECHO),
                        columna_ordenable("Nº títulos", "num_titulos", padding_x=PADDING_ESTRECHO),
                        columna_ordenable("Precio medio", "precio_medio"),
                        columna_ordenable("Cotización", "cotizacion_actual"),
                        columna_ordenable("Valor mercado", "valor_mercado"),
                        columna_ordenable("Plusvalía (€)", "plusvalia_eur"),
                        columna_ordenable("Plusvalía (%)", "plusvalia_pct"),
                        columna_ordenable("YOC año anterior", "yoc_anterior"),
                        columna_ordenable("Peso", "peso_cartera_pct"),
                    ),
                ),
                rx.table.body(rx.foreach(CarteraState.tenencias_filtradas, fila_tenencia)),
                width="100%",
                height="75vh",
                min_width="0",
            ),
            rx.cond(
                CarteraState.tenencias_filtradas.length() == 0,
                rx.text(
                    "No hay valores en cartera todavía.",
                    color_scheme="gray",
                    size="2",
                    padding_y=SPACE_MD,
                ),
            ),
            tabla_valores_liquidados(),
            direction="column",
            spacing="4",
            padding="1em",
        ),
        size="4",
    )


def cartera() -> rx.Component:
    return requiere_login(pagina_cartera())

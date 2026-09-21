"""Página VALOR (/valor/[id_valor]): detalle de un único valor --
cabecera, resumen con TIR individual (con y sin revalorización),
rentabilidad por año, operaciones por año y listado completo de
operaciones de ese valor. Se accede pulsando una fila de la página
CARTERA.
"""

import reflex as rx

from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.header import header
from gestion_cartera.components.scroll_x import scroll_x
from gestion_cartera.states.valor_detalle_state import ValorDetalleState
from gestion_cartera.styles import LINK_COLOR, SPACE_MD, SPACE_SM


def tarjeta(titulo: str, valor, color=None) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.text(titulo, size="2", color_scheme="gray", weight="medium"),
            rx.heading(valor, size="5", color=color) if color is not None else rx.heading(valor, size="5"),
            direction="column",
            spacing="1",
        ),
    )


def cabecera_valor() -> rx.Component:
    r = ValorDetalleState.resumen
    return rx.flex(
        rx.link(
            rx.hstack(
                rx.icon(tag="arrow-left", size=16),
                rx.text("Volver a Cartera"),
                spacing="1",
            ),
            href="/cartera",
            # Ver el comentario en components/header.py sobre por qué el
            # hover se aplica con la clase ".app-link" (theme.css) y no
            # con color=/_hover= de Reflex.
            class_name="app-link",
        ),
        rx.flex(
            rx.hstack(
                # Logo vía Logo.dev (a partir del ticker, ver
                # services/company_logo.py ).
                # Nunca llega vacío: si no hay logo real, Logo.dev
                # sirve un monograma en su lugar.
                rx.image(
                    src=r["logo_url"],
                    alt="",
                    width="48px",
                    height="48px",
                    border_radius="8px",
                    object_fit="contain",
                ),
                rx.flex(
                    rx.hstack(
                        rx.heading(r["ticker"], size="7"),
                        rx.icon_button(
                            rx.icon(tag="pencil", size=14),
                            variant="ghost",
                            color_scheme="gray",
                            size="1",
                            type="button",
                            on_click=ValorDetalleState.abrir_editar_ticker,
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.text(r["empresa"], size="4", color_scheme="gray"),
                    rx.text(f"{r['zona']} · {r['mercado']}", size="2", color_scheme="gray"),
                    direction="column",
                    spacing="1",
                ),
                spacing="3",
                align="center",
            ),
            rx.spacer(),
            rx.flex(
                rx.text("Cotización actual", size="2", color_scheme="gray"),
                rx.heading(r["cotizacion_actual_mostrar"], size="6"),
                # Solo se muestra cuando la divisa original no es el
                # euro (si no, sería repetir el mismo número); ver
                # valor_db.obtener_resumen_valor.
                rx.cond(
                    r["cotizacion_divisa_mostrar"] != "",
                    rx.text(
                        r["cotizacion_divisa_mostrar"],
                        size="2",
                        color_scheme="gray",
                        weight="medium",
                    ),
                ),
                rx.text(
                    f"Actualizada: {r['cotizacion_actualizada_en']}",
                    size="1",
                    color_scheme="gray",
                ),
                direction="column",
                spacing="1",
                align="end",
            ),
            rx.spacer(),
            rx.flex(
                rx.badge(r["supersector"], variant="soft"),
                rx.badge(r["sector"], variant="soft", color_scheme="gray"),
                rx.badge(r["grupo"], variant="soft", color_scheme="gray"),
                spacing="2",
                align="end",
                wrap="wrap",
            ),
            width="100%",
            wrap="wrap",
            justify="between",
            align="start",
            gap="1em",
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def dialogo_editar_ticker() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.flex(
                rx.heading("Editar ticker / mercado", size="4"),
                rx.text(
                    "Útil si la empresa ha cambiado de símbolo bursátil o ha trasladado "
                    "su cotización a otro mercado. Afecta a todo el histórico de "
                    "operaciones de este valor (se identifican por id, no por ticker) y "
                    "fuerza a pedir la cotización de nuevo con el símbolo actualizado.",
                    size="1",
                    color_scheme="gray",
                ),
                rx.grid(
                    rx.flex(
                        rx.text("Ticker", size="2", weight="medium", color_scheme="gray"),
                        rx.input(
                            value=ValorDetalleState.editando_ticker,
                            on_change=ValorDetalleState.set_editando_ticker,
                            width="100%",
                        ),
                        direction="column",
                        spacing="1",
                        width="100%",
                    ),
                    rx.flex(
                        rx.text("Mercado", size="2", weight="medium", color_scheme="gray"),
                        rx.select(
                            ValorDetalleState.mercados_disponibles,
                            value=ValorDetalleState.editando_mercado,
                            on_change=ValorDetalleState.set_editando_mercado,
                            width="100%",
                        ),
                        direction="column",
                        spacing="1",
                        width="100%",
                    ),
                    columns=rx.breakpoints(initial="1", sm="2"),
                    spacing="3",
                    width="100%",
                ),
                rx.cond(
                    ValorDetalleState.editar_ticker_error != "",
                    rx.callout(
                        ValorDetalleState.editar_ticker_error, color_scheme="red", size="1"
                    ),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("Cancelar", variant="soft", color_scheme="gray", type="button")
                    ),
                    rx.spacer(),
                    rx.button(
                        "Guardar cambios", on_click=ValorDetalleState.guardar_ticker_mercado
                    ),
                    spacing="3",
                    width="100%",
                    padding_top=SPACE_SM,
                ),
                direction="column",
                spacing="4",
            ),
        ),
        open=ValorDetalleState.editar_ticker_open,
        on_open_change=ValorDetalleState.set_editar_ticker_open,
    )


def resumen_numeros() -> rx.Component:
    r = ValorDetalleState.resumen
    return rx.grid(
        tarjeta("Nº títulos", r["num_titulos_mostrar"]),
        tarjeta("Inversión", r["valor_compra_mostrar"]),
        tarjeta("Precio medio", r["precio_medio_mostrar"]),
        tarjeta("Valor actual", r["valor_mercado_mostrar"]),
        rx.card(
            rx.flex(
                rx.text("Plusvalía", size="2", color_scheme="gray", weight="medium"),
                rx.heading(r["plusvalia_eur_mostrar"], size="5", color=r["color_plusvalia"]),
                rx.text(
                    r["plusvalia_pct_mostrar"],
                    size="2",
                    weight="medium",
                    color=r["color_plusvalia"],
                ),
                direction="column",
                spacing="1",
            ),
        ),
        rx.card(
            rx.flex(
                rx.text("TIR (con revalorización)", size="2", color_scheme="gray", weight="medium"),
                rx.heading(r["tir_con_revalorizacion_mostrar"], size="5"),
                rx.text(
                    f"Sin revalorización: {r['tir_sin_revalorizacion_mostrar']}",
                    size="1",
                    color_scheme="gray",
                ),
                direction="column",
                spacing="1",
            ),
        ),
        tarjeta("Dividendos acumulados", r["dividendos_acumulados_mostrar"]),
        tarjeta("Venta de derechos acumulada", r["venta_derechos_acumulada_mostrar"]),
        tarjeta("Total ingresos", r["total_ingresos_mostrar"]),
        # Incluso en pantalla estrecha se ven 2 tarjetas por fila (no 1),
        # subiendo progresivamente hasta las 5 que caben cómodas en
        # pantalla ancha -- a petición expresa, en vez del salto brusco
        # 1 -> 2 -> 3 -> 5 que había antes.
        columns=rx.breakpoints(initial="2", xs="2", sm="3", md="4", lg="5"),
        spacing="3",
        width="100%",
    )


def fila_rentabilidad_anio(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["anio"], weight="medium"),
        rx.table.cell(item["titulos_cierre_mostrar"]),
        rx.table.cell(item["precio_medio_cierre_mostrar"]),
        rx.table.cell(item["dividendos_anio_mostrar"]),
        rx.table.cell(item["yoc_mostrar"]),
        rx.table.cell(item["rd_mostrar"]),
    )


def tabla_rentabilidad_por_anio() -> rx.Component:
    return rx.flex(
        rx.heading("Rentabilidad por año", size="4"),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Año"),
                        rx.table.column_header_cell("Títulos a cierre"),
                        rx.table.column_header_cell("Precio medio"),
                        rx.table.column_header_cell("Dividendos + Derechos"),
                        rx.table.column_header_cell("YOC"),
                        rx.table.column_header_cell("R.D."),
                    )
                ),
                rx.table.body(
                    rx.foreach(ValorDetalleState.rentabilidad_por_anio, fila_rentabilidad_anio)
                ),
                width="100%",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def fila_operaciones_anio(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["anio"], weight="medium"),
        rx.table.cell(f"{item['compra_titulos_mostrar']} / {item['compra_importe_mostrar']}"),
        rx.table.cell(f"{item['script_cpa_titulos_mostrar']} / {item['script_cpa_importe_mostrar']}"),
        rx.table.cell(f"{item['script_venta_titulos_mostrar']} / {item['script_venta_importe_mostrar']}"),
        rx.table.cell(item["total_titulos_mostrar"], weight="medium"),
        rx.table.cell(item["total_importe_mostrar"], weight="medium"),
    )


def tabla_operaciones_por_anio() -> rx.Component:
    return rx.flex(
        rx.heading("Operaciones por año", size="4"),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Año"),
                        rx.table.column_header_cell("Compra (títulos / importe)"),
                        rx.table.column_header_cell("Script compra (títulos / importe)"),
                        rx.table.column_header_cell("Script venta (títulos / importe)"),
                        rx.table.column_header_cell("Total títulos"),
                        rx.table.column_header_cell("Total importe"),
                    )
                ),
                rx.table.body(
                    rx.foreach(ValorDetalleState.operaciones_por_anio, fila_operaciones_anio)
                ),
                width="100%",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def _grafico_cotizacion(titulo: str, datos: rx.Var, vacio_texto: str) -> rx.Component:
    """Gráfico de área de un único punto por fecha -- pensado para
    reutilizarse en `grafico_mensual`/`grafico_anual` (mismos ejes y
    estilo, solo cambian el título y la serie de datos). Una sola
    serie -> sin leyenda (el título ya la identifica); línea fina,
    rejilla discreta y tooltip al pasar el ratón, ya que el propio
    gráfico HTML es interactivo."""
    return rx.flex(
        rx.heading(titulo, size="4"),
        rx.cond(
            datos.length() > 0,
            rx.recharts.responsive_container(
                rx.recharts.area_chart(
                    rx.recharts.cartesian_grid(
                        stroke_dasharray="3 3", vertical=False, stroke="var(--app-separator)"
                    ),
                    rx.recharts.x_axis(
                        data_key="fecha",
                        stroke="var(--gray-9)",
                        tick_line=False,
                        axis_line=False,
                        min_tick_gap=24,
                    ),
                    rx.recharts.y_axis(
                        stroke="var(--gray-9)",
                        tick_line=False,
                        axis_line=False,
                        domain=["auto", "auto"],
                        width=68,
                    ),
                    rx.recharts.graphing_tooltip(),
                    rx.recharts.area(
                        data_key="precio",
                        name="Cotización (€)",
                        type_="monotone",
                        stroke=LINK_COLOR,
                        stroke_width=2,
                        # Token alpha de Radix (no `fill_opacity`, que
                        # Recharts ignora vía props de Reflex): así el
                        # área queda sutil sin tapar la rejilla, y
                        # ajusta solo por su cuenta en modo oscuro.
                        fill="var(--accent-a3)",
                        dot=False,
                        active_dot={"r": 4},
                    ),
                    data=datos,
                    margin={"top": 8, "right": 12, "left": 0, "bottom": 0},
                ),
                width="100%",
                height=260,
            ),
            rx.flex(
                rx.cond(
                    ValorDetalleState.cargando_historico,
                    rx.hstack(
                        rx.spinner(size="2"),
                        rx.text("Cargando cotización…", size="2", color_scheme="gray"),
                        spacing="2",
                        align="center",
                    ),
                    rx.text(vacio_texto, size="2", color_scheme="gray"),
                ),
                align="center",
                justify="center",
                height="260px",
                width="100%",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def grafico_mensual() -> rx.Component:
    return _grafico_cotizacion(
        "Cotización — último mes",
        ValorDetalleState.historico_mensual,
        "No hay datos de cotización del último mes.",
    )


def grafico_anual() -> rx.Component:
    return _grafico_cotizacion(
        "Cotización — último año",
        ValorDetalleState.historico_anual,
        "No hay datos de cotización del último año.",
    )


def graficos_cotizacion() -> rx.Component:
    return rx.flex(
        rx.cond(
            ValorDetalleState.historico_error != "",
            rx.callout(ValorDetalleState.historico_error, color_scheme="amber", size="1"),
        ),
        rx.grid(
            grafico_mensual(),
            grafico_anual(),
            columns=rx.breakpoints(initial="1", lg="2"),
            spacing="4",
            width="100%",
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def fila_operacion(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["tipo_operacion"]),
        rx.table.cell(item["fecha_mostrar"]),
        rx.table.cell(item["num_titulos_mostrar"]),
        rx.table.cell(item["broker"]),
        rx.table.cell(item["observaciones"], size="1", color_scheme="gray"),
    )


def tabla_operaciones() -> rx.Component:
    return rx.flex(
        rx.heading("Todas las operaciones", size="4"),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Tipo"),
                        rx.table.column_header_cell("Fecha"),
                        rx.table.column_header_cell("Nº títulos"),
                        rx.table.column_header_cell("Bróker"),
                        rx.table.column_header_cell("Observaciones"),
                    )
                ),
                rx.table.body(rx.foreach(ValorDetalleState.operaciones, fila_operacion)),
                width="100%",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def pagina_valor_detalle() -> rx.Component:
    return rx.container(
        header(extra_on_portfolio_change=[ValorDetalleState.cargar_datos]),
        rx.cond(
            ValorDetalleState.no_encontrado,
            rx.flex(
                rx.text("No se ha encontrado este valor en la cartera seleccionada.", size="3"),
                rx.link(rx.button("Volver a Cartera"), href="/cartera"),
                direction="column",
                spacing="3",
                padding="1em",
            ),
            rx.flex(
                cabecera_valor(),
                dialogo_editar_ticker(),
                resumen_numeros(),
                graficos_cotizacion(),
                tabla_rentabilidad_por_anio(),
                tabla_operaciones_por_anio(),
                tabla_operaciones(),
                direction="column",
                spacing="5",
                padding="1em",
            ),
        ),
        size="4",
    )


def valor_detalle() -> rx.Component:
    return requiere_login(pagina_valor_detalle())

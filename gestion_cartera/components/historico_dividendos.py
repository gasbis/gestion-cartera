"""Tarjeta "Histórico de dividendos" de la página RADAR: ranking de los
valores en cartera y en el radar según el comportamiento de su
dividendo (ver historico_dividendos_db.py), ordenable por cualquier
columna, con una ficha por valor (gráfico del dividendo de cada año y
conclusión) que se abre al pulsar la fila.

La ficha va en un diálogo, no desplegada dentro de la tabla: la tabla
es ancha y en el móvil se desplaza en horizontal, y una ficha dentro de
ella quedaría cortada.
"""

import reflex as rx

from gestion_cartera.components.scroll_x import scroll_x
from gestion_cartera.historico_dividendos_db import (
    PESO_CRECIMIENTO,
    PESO_FIABILIDAD,
    PESO_REGULARIDAD,
    PESO_RENTABILIDAD,
    PESO_VALORACION,
    UMBRAL_AMBAR,
    UMBRAL_VERDE,
)
from gestion_cartera.states.historico_dividendos_state import HistoricoDividendosState as S


def _color_texto(color: rx.Var) -> rx.Var:
    return rx.match(
        color,
        ("green", rx.color("green", 11)),
        ("red", rx.color("red", 11)),
        rx.color("gray", 12),
    )


def _badge_puntuacion(texto: rx.Var, color: rx.Var) -> rx.Component:
    def _b(scheme: str) -> rx.Component:
        return rx.badge(texto, color_scheme=scheme, variant="soft", size="2", min_width="2.6em", justify="center")

    return rx.match(
        color,
        ("green", _b("green")),
        ("amber", _b("amber")),
        ("red", _b("red")),
        _b("gray"),
    )


def _cabecera(texto: str, columna: str, alinear: str = "right", ayuda: str = "") -> rx.Component:
    activa = S.orden == columna
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(texto, title=ayuda or None),
            rx.cond(
                activa,
                rx.cond(S.orden_desc, rx.icon("arrow-down", size=12), rx.icon("arrow-up", size=12)),
            ),
            spacing="1",
            align="center",
            justify="end" if alinear == "right" else "start",
            cursor="pointer",
            on_click=S.ordenar_por(columna),
            white_space="nowrap",
        ),
        text_align=alinear,
    )


def _celda_num(texto: rx.Var, color: rx.Var | None = None) -> rx.Component:
    return rx.table.cell(
        texto,
        text_align="right",
        white_space="nowrap",
        color=_color_texto(color) if color is not None else None,
    )


def _fila(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.flex(
                rx.text(item["ticker"], weight="medium"),
                rx.text(item["empresa"], size="1", color_scheme="gray"),
                direction="column",
            ),
            min_width="9em",
        ),
        rx.table.cell(rx.text(item["origen_mostrar"], size="1", color_scheme="gray"), white_space="nowrap"),
        rx.table.cell(_badge_puntuacion(item["puntuacion_mostrar"], item["color_puntuacion"]), text_align="center"),
        _celda_num(item["rent_actual_mostrar"]),
        _celda_num(item["vs_media_mostrar"], item["color_vs_media"]),
        _celda_num(item["cagr_mostrar"], item["color_cagr"]),
        _celda_num(item["sin_recortes_mostrar"]),
        _celda_num(item["recortes_mostrar"]),
        rx.table.cell(item["regularidad_mostrar"], white_space="nowrap"),
        _celda_num(item["yoc_mostrar"]),
        rx.table.cell(rx.icon("chevron-right", size=16, color=rx.color("gray", 9))),
        cursor="pointer",
        on_click=S.abrir_ficha(item["id_valor"]),
        _hover={"background_color": rx.color("gray", 3)},
    )


def _grafico_ficha() -> rx.Component:
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            rx.recharts.label_list(data_key="dpa_mostrar", position="top", fill=rx.color("gray", 11), font_size=10),
            rx.foreach(S.detalle_grafico, lambda d: rx.recharts.cell(fill=d["color"])),
            data_key="dpa",
            name="Dividendo por acción",
            radius=[4, 4, 0, 0],
        ),
        rx.recharts.x_axis(data_key="anio", tick_line=False, font_size=11, interval=0),
        rx.recharts.y_axis(hide=True),
        data=S.detalle_grafico,
        margin={"top": 20, "left": 4, "right": 4},
        width="100%",
        height=220,
    )


def _leyenda_item(color: str, texto: str) -> rx.Component:
    return rx.hstack(
        rx.box(width="10px", height="10px", border_radius="2px", background_color=color),
        rx.text(texto, size="1", color_scheme="gray"),
        spacing="1",
        align="center",
    )


def _ficha() -> rx.Component:
    d = S.detalle
    return rx.dialog.root(
        rx.dialog.content(
            rx.flex(
                rx.hstack(
                    rx.flex(
                        rx.dialog.title(d["ticker"], margin="0"),
                        rx.text(d["empresa"], size="2", color_scheme="gray"),
                        rx.text(d["origen_mostrar"], size="1", color_scheme="gray"),
                        direction="column",
                    ),
                    rx.spacer(),
                    rx.flex(
                        _badge_puntuacion(d["puntuacion_mostrar"], d["color_puntuacion"]),
                        rx.text("puntuación", size="1", color_scheme="gray"),
                        direction="column",
                        align="center",
                    ),
                    width="100%",
                    align="start",
                ),
                rx.callout(d["conclusion"], icon="lightbulb", size="1", color_scheme="blue"),
                rx.text("Dividendo por acción de cada año", size="2", weight="medium"),
                rx.cond(
                    S.detalle_grafico.length() > 0,
                    rx.fragment(
                        _grafico_ficha(),
                        rx.hstack(
                            _leyenda_item("var(--accent-9)", "Yahoo Finance"),
                            _leyenda_item("var(--amber-9)", "Completado con tus cobros"),
                            _leyenda_item("var(--gray-8)", "Últimos 12 meses"),
                            spacing="4",
                            wrap="wrap",
                            justify="center",
                            width="100%",
                        ),
                    ),
                    rx.text("Sin datos para dibujar.", size="2", color_scheme="gray"),
                ),
                rx.cond(
                    S.detalle_datos.length() > 0,
                    rx.grid(
                        rx.foreach(
                            S.detalle_datos,
                            lambda x: rx.flex(
                                rx.text(x["etiqueta"], size="1", color_scheme="gray"),
                                rx.text(x["valor"], size="2", weight="medium"),
                                direction="column",
                            ),
                        ),
                        columns=rx.breakpoints(initial="2", sm="3"),
                        spacing="3",
                        width="100%",
                    ),
                ),
                rx.cond(
                    d["notas"] != "",
                    rx.text(d["notas"], size="1", color_scheme="gray"),
                ),
                rx.flex(
                    rx.dialog.close(rx.button("Cerrar", variant="soft", color_scheme="gray")),
                    justify="end",
                ),
                direction="column",
                spacing="3",
            ),
            max_width="620px",
        ),
        open=S.expandido != -1,
        on_open_change=S.cambiar_ficha_abierta,
    )


def _explicacion() -> rx.Component:
    """Cómo se calcula cada columna y la puntuación (desplegable)."""
    parrafos = [
        "Se usan los 10 últimos años completos, en la divisa de cada valor (sin efecto del "
        "tipo de cambio). Fuente: Yahoo Finance; en los valores en euros, los años que "
        "tuviste enteros se completan con tus cobros si Yahoo da menos (le pasa con algunos "
        "scrips).",
        "Rent. actual: dividendo de los últimos 12 meses entre la última cotización.",
        "Vs. media: rentabilidad actual menos su media de los 5 últimos años, en puntos. "
        "En verde, paga más de lo habitual (barata respecto a su propia historia); en rojo, "
        "menos (cara, o el dividendo ha bajado).",
        "Crec. 5a: crecimiento anual compuesto del dividendo en 5 años.",
        "Sin recortes: años seguidos, hasta el último, sin bajar el dividendo más de un "
        "10 %. Recortes: años con una bajada mayor en todo el periodo.",
        "Regularidad: mitad por los años con pago, mitad por lo estable que es la "
        "evolución del dividendo.",
        "YoC: dividendo de los últimos 12 meses sobre tu precio medio de compra (solo los "
        "que tienes en cartera).",
        f"Puntuación (0-100): rentabilidad actual hasta {PESO_RENTABILIDAD} puntos (máximo con "
        f"un 6 %), vs. media hasta {PESO_VALORACION}, crecimiento hasta {PESO_CRECIMIENTO} "
        f"(de -5 % a +10 % anual), años sin recorte hasta {PESO_FIABILIDAD} y regularidad "
        f"hasta {PESO_REGULARIDAD}. Verde desde {UMBRAL_VERDE}, ámbar desde {UMBRAL_AMBAR}. "
        "Es una ayuda para ordenar, no una recomendación: no tiene en cuenta la deuda, el "
        "payout ni las perspectivas de la empresa.",
    ]
    return rx.accordion.root(
        rx.accordion.item(
            header="¿Cómo se calcula?",
            content=rx.flex(
                *[rx.text(p, size="1", color_scheme="gray") for p in parrafos],
                direction="column",
                spacing="2",
            ),
            value="explicacion",
        ),
        collapsible=True,
        type="single",
        variant="ghost",
        width="100%",
    )


def historico_dividendos_section() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.flex(
                rx.heading("Histórico de dividendos", size="3"),
                rx.spacer(),
                rx.cond(
                    S.cargando,
                    rx.hstack(
                        rx.spinner(size="1"),
                        rx.text(S.progreso, size="1", color_scheme="gray"),
                        spacing="2",
                        align="center",
                    ),
                ),
                rx.button(
                    rx.icon("refresh-cw", size=14),
                    "Recalcular",
                    size="1",
                    variant="soft",
                    disabled=S.cargando,
                    on_click=S.recalcular,
                ),
                align="center",
                width="100%",
                wrap="wrap",
                gap="0.5em",
            ),
            rx.text(
                "Ranking de los valores en cartera y en el radar según el comportamiento de su "
                "dividendo en los últimos 10 años. Pulsa una columna para ordenar y una fila "
                "para ver su ficha.",
                size="1",
                color_scheme="gray",
            ),
            rx.segmented_control.root(
                rx.segmented_control.item("Todos", value="todos"),
                rx.segmented_control.item(f"En cartera ({S.num_en_cartera})", value="cartera"),
                rx.segmented_control.item(f"En el radar ({S.num_en_radar})", value="radar"),
                value=S.filtro,
                on_change=S.set_filtro,
                size="1",
            ),
            rx.cond(
                S.error != "",
                rx.callout(S.error, color_scheme="amber", size="1"),
            ),
            rx.cond(
                S.filas_visibles.length() > 0,
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                _cabecera("Valor", "ticker", alinear="left"),
                                rx.table.column_header_cell("Origen"),
                                _cabecera("Punt.", "puntuacion", ayuda="Puntuación global (0-100)"),
                                _cabecera("Rent. actual", "rent_actual"),
                                _cabecera("Vs. media", "vs_media", ayuda="Frente a su media de 5 años"),
                                _cabecera("Crec. 5a", "cagr"),
                                _cabecera("Sin recortes", "sin_recortes"),
                                _cabecera("Recortes", "recortes"),
                                _cabecera("Regularidad", "regularidad", alinear="left"),
                                _cabecera("YoC", "yoc"),
                                rx.table.column_header_cell(""),
                            )
                        ),
                        rx.table.body(rx.foreach(S.filas_visibles, _fila)),
                        size="1",
                        width="100%",
                        overflow="visible",
                    ),
                ),
                rx.text(
                    rx.cond(S.cargando, "Calculando…", "No hay valores que mostrar."),
                    size="2",
                    color_scheme="gray",
                ),
            ),
            _explicacion(),
            _ficha(),
            direction="column",
            spacing="3",
        ),
        width="100%",
    )

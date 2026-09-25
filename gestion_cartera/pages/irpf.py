"""Página IRPF (/irpf): resumen pensado para ayudar a confeccionar la
declaración de la renta del año fiscal seleccionado -- dividendos y
venta de derechos cobrados con sus retenciones, y plusvalías realizadas
en ventas (por lotes FIFO). Combina SIEMPRE las dos carteras del
usuario (ver resumen_irpf_db.py), así que -- a diferencia del resto de
páginas -- no lleva el selector de cartera del header (ver
components/header.py, mostrar_selector_cartera).
"""

import reflex as rx

from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.header import header
from gestion_cartera.components.page_title import page_title
from gestion_cartera.components.scroll_x import scroll_x
from gestion_cartera.components.stat_card import stat_card
from gestion_cartera.states.irpf_state import IrpfState
from gestion_cartera.styles import SPACE_SM


def selector_anio() -> rx.Component:
    return rx.flex(
        rx.flex(
            rx.text("Año fiscal:", size="2", weight="medium"),
            rx.select(
                IrpfState.anios_disponibles,
                value=IrpfState.anio_seleccionado,
                on_change=IrpfState.set_anio_seleccionado,
            ),
            align="center",
            spacing="2",
        ),
        rx.spacer(),
        rx.button(
            rx.icon(tag="download", size=16),
            "Descargar Excel",
            variant="soft",
            on_click=IrpfState.descargar_excel,
        ),
        align="center",
        width="100%",
        wrap="wrap",
        gap="0.75em",
    )


def resumen_totales() -> rx.Component:
    t = IrpfState.totales
    return rx.grid(
        stat_card("Dividendos + venta de derechos", t["total_bruto_dividendos_mostrar"]),
        stat_card("Retención en destino", t["total_retencion_destino_mostrar"]),
        stat_card(
            "Retención en origen (hasta 15%)", t["total_retencion_origen_hasta15_mostrar"]
        ),
        stat_card(
            "Retención en origen (exceso sobre 15%)",
            t["total_retencion_origen_exceso_mostrar"],
        ),
        stat_card(
            "Plusvalía de ventas",
            t["total_plusvalia_ventas_mostrar"],
            value_color=t["color_total_plusvalia_ventas"],
        ),
        columns=rx.breakpoints(initial="2", xs="2", sm="3", lg="5"),
        spacing="3",
        width="100%",
    )


def fila_dividendo(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["fecha_mostrar"]),
        rx.table.cell(item["cartera"], size="1", color_scheme="gray"),
        rx.table.cell(item["ticker"], weight="medium"),
        rx.table.cell(item["empresa"]),
        rx.table.cell(item["tipo"]),
        rx.table.cell(item["importe_mostrar"], text_align="right"),
        rx.table.cell(item["retencion_destino_mostrar"], text_align="right"),
        rx.table.cell(item["retencion_origen_hasta15_mostrar"], text_align="right"),
        rx.table.cell(item["retencion_origen_exceso_mostrar"], text_align="right"),
    )


def tabla_dividendos() -> rx.Component:
    return rx.flex(
        rx.heading("Dividendos y venta de derechos", size="4"),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Fecha"),
                        rx.table.column_header_cell("Cartera"),
                        rx.table.column_header_cell("Ticker"),
                        rx.table.column_header_cell("Empresa"),
                        rx.table.column_header_cell("Tipo"),
                        rx.table.column_header_cell("Bruto", text_align="right"),
                        rx.table.column_header_cell("Ret. destino", text_align="right"),
                        rx.table.column_header_cell("Ret. origen ≤15%", text_align="right"),
                        rx.table.column_header_cell("Ret. origen >15%", text_align="right"),
                    )
                ),
                rx.table.body(rx.foreach(IrpfState.listado_dividendos, fila_dividendo)),
                width="100%",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def fila_exceso_zona(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["zona"], weight="medium"),
        rx.table.cell(item["importe_mostrar"], text_align="right"),
    )


def tabla_exceso_origen() -> rx.Component:
    return rx.flex(
        rx.heading("Exceso de retención en origen por zona / mercado", size="4"),
        rx.callout(
            "Esta agrupación es orientativa: se hace por la zona del valor (desglosada por "
            "mercado dentro de la zona EURO) y puede no coincidir exactamente con el país de "
            "residencia fiscal real de la empresa -- por ejemplo, una acción que cotiza en "
            "EE. UU. puede ser de una empresa domiciliada en otro país. Antes de presentar la "
            "declaración, comprueba siempre el certificado de retenciones de tu bróker.",
            icon="info",
            color_scheme="amber",
            size="1",
        ),
        rx.cond(
            IrpfState.exceso_origen_por_zona.length() > 0,
            scroll_x(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Zona / mercado"),
                            rx.table.column_header_cell("Exceso sobre 15%", text_align="right"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(IrpfState.exceso_origen_por_zona, fila_exceso_zona)
                    ),
                    width="100%",
                ),
            ),
            rx.text(
                "Ninguna retención en origen supera el 15% del bruto cobrado este año.",
                size="2",
                color_scheme="gray",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def fila_venta(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["fecha_mostrar"]),
        rx.table.cell(item["cartera"], size="1", color_scheme="gray"),
        rx.table.cell(item["ticker"], weight="medium"),
        rx.table.cell(item["empresa"]),
        rx.table.cell(item["num_titulos_mostrar"], text_align="right"),
        rx.table.cell(item["importe_venta_mostrar"], text_align="right"),
        rx.table.cell(item["coste_mostrar"], text_align="right"),
        rx.table.cell(
            item["plusvalia_mostrar"], text_align="right", color=item["color_plusvalia"]
        ),
    )


def tabla_ventas() -> rx.Component:
    return rx.flex(
        rx.heading("Ventas (plusvalía por lotes FIFO)", size="4"),
        rx.text(
            "Cada venta consume primero los títulos comprados más antiguos (FIFO): el coste "
            "y la plusvalía de cada fila ya tienen esto en cuenta.",
            size="1",
            color_scheme="gray",
        ),
        scroll_x(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Fecha"),
                        rx.table.column_header_cell("Cartera"),
                        rx.table.column_header_cell("Ticker"),
                        rx.table.column_header_cell("Empresa"),
                        rx.table.column_header_cell("Nº títulos", text_align="right"),
                        rx.table.column_header_cell("Importe venta", text_align="right"),
                        rx.table.column_header_cell("Coste (FIFO)", text_align="right"),
                        rx.table.column_header_cell("Plusvalía", text_align="right"),
                    )
                ),
                rx.table.body(rx.foreach(IrpfState.listado_ventas, fila_venta)),
                width="100%",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def pagina_irpf() -> rx.Component:
    return rx.container(
        header(),
        rx.flex(
            rx.flex(
                page_title(
                    "IRPF",
                    "Resumen del año fiscal seleccionado para ayudarte a confeccionar la "
                    "declaración de la renta, combinando siempre las dos carteras.",
                ),
                selector_anio(),
                direction="column",
                spacing="3",
                width="100%",
            ),
            rx.skeleton(resumen_totales(), loading=IrpfState.cargando),
            rx.skeleton(tabla_dividendos(), loading=IrpfState.cargando),
            rx.skeleton(tabla_exceso_origen(), loading=IrpfState.cargando),
            rx.skeleton(tabla_ventas(), loading=IrpfState.cargando),
            direction="column",
            spacing="6",
            padding="1em",
            padding_top=SPACE_SM,
        ),
        size="4",
    )


def irpf() -> rx.Component:
    return requiere_login(pagina_irpf())

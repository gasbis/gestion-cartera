"""Página OPERACIONES: listado (buscador + orden por columna), el botón
que abre el formulario de alta en un diálogo, y el diálogo de edición /
eliminación de una operación existente.
"""

import reflex as rx

from gestion_cartera.components.alta_operacion_form import (
    AltaOperacionState,
    alta_operacion_form,
    campo,
    campo_calculado,
)
from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.header import header
from gestion_cartera.components.page_title import page_title
from gestion_cartera.states.operaciones_state import OperacionesState
from gestion_cartera.styles import SPACE_MD, SPACE_SM, STICKY_TABLE_HEADER


def columna_ordenable(label: str, campo_nombre: str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(label, weight="medium", size="2"),
            rx.cond(
                OperacionesState.orden_campo == campo_nombre,
                rx.icon(
                    tag=rx.cond(OperacionesState.orden_desc, "chevron-down", "chevron-up"),
                    size=14,
                ),
            ),
            spacing="1",
            align="center",
        ),
        on_click=OperacionesState.set_orden(campo_nombre),
        cursor="pointer",
        user_select="none",
        **STICKY_TABLE_HEADER,
    )


def fila_operacion(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["tipo_operacion"]),
        rx.table.cell(item["fecha_mostrar"]),
        rx.table.cell(item["ticker"]),
        rx.table.cell(item["empresa"]),
        rx.table.cell(item["num_titulos_mostrar"]),
        rx.table.cell(item["broker"]),
        on_click=OperacionesState.abrir_edicion(item),
        style={"cursor": "pointer"},
        _hover={"background_color": "var(--gray-a2)"},
    )


def campo_editar_broker() -> rx.Component:
    return campo(
        "Bróker",
        rx.cond(
            OperacionesState.brokers_disponibles.length() > 0,
            rx.select(
                OperacionesState.brokers_disponibles,
                value=OperacionesState.editando_broker,
                on_change=OperacionesState.set_editando_broker,
                width="100%",
            ),
            rx.text("Cargando brókers…", size="2", color_scheme="gray"),
        ),
    )


def campos_editar_compra_venta_prima() -> rx.Component:
    return rx.grid(
        campo(
            "Nº títulos",
            rx.input(
                type="number",
                value=OperacionesState.editando_num_titulos,
                on_change=OperacionesState.set_editando_num_titulos,
                width="100%",
            ),
        ),
        campo(
            "Importe (€)",
            rx.input(
                type="number",
                value=OperacionesState.editando_importe,
                on_change=OperacionesState.set_editando_importe,
                width="100%",
            ),
        ),
        campo_calculado("Importe unitario (€)", OperacionesState.editando_importe_unitario),
        columns=rx.breakpoints(initial="1", md="3"),
        spacing="3",
        width="100%",
    )


def campos_editar_dividendo() -> rx.Component:
    return rx.flex(
        rx.grid(
            campo(
                "Nº títulos",
                rx.input(
                    type="number",
                    value=OperacionesState.editando_num_titulos,
                    on_change=OperacionesState.set_editando_num_titulos,
                    width="100%",
                ),
            ),
            campo(
                "Importe (€)",
                rx.input(
                    type="number",
                    value=OperacionesState.editando_importe,
                    on_change=OperacionesState.set_editando_importe,
                    width="100%",
                ),
            ),
            campo_calculado("Importe unitario (€)", OperacionesState.editando_importe_unitario),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="3",
            width="100%",
        ),
        rx.grid(
            campo(
                "Retención origen (€)",
                rx.input(
                    type="number",
                    value=OperacionesState.editando_retencion_origen,
                    on_change=OperacionesState.set_editando_retencion_origen,
                    width="100%",
                ),
            ),
            campo(
                "Retención destino (€)",
                rx.input(
                    type="number",
                    value=OperacionesState.editando_retencion_destino,
                    on_change=OperacionesState.set_editando_retencion_destino,
                    width="100%",
                ),
            ),
            campo_calculado(
                "Importe neto (€)",
                OperacionesState.editando_importe_neto,
                nota="Solo informativo, no se guarda.",
            ),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="3",
            width="100%",
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def campos_editar_script() -> rx.Component:
    return rx.flex(
        campo(
            "Tipo de derecho",
            rx.segmented_control.root(
                rx.segmented_control.item("Compra de derechos", value="Compra"),
                rx.segmented_control.item("Venta de derechos", value="Venta"),
                value=OperacionesState.editando_tipo_derecho_script,
                on_change=OperacionesState.set_editando_tipo_derecho_script,
            ),
        ),
        rx.grid(
            campo(
                "Nº títulos recibidos",
                rx.input(
                    type="number",
                    value=OperacionesState.editando_num_titulos,
                    on_change=OperacionesState.set_editando_num_titulos,
                    width="100%",
                ),
            ),
            campo(
                rx.cond(
                    OperacionesState.editando_tipo_derecho_script == "Compra",
                    "Importe compra derechos (€)",
                    "Importe venta derechos (€)",
                ),
                rx.input(
                    type="number",
                    value=OperacionesState.editando_importe,
                    on_change=OperacionesState.set_editando_importe,
                    width="100%",
                ),
            ),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="3",
            width="100%",
        ),
        rx.cond(
            OperacionesState.editando_tipo_derecho_script == "Venta",
            rx.grid(
                campo(
                    "Retención origen (€)",
                    rx.input(
                        type="number",
                        value=OperacionesState.editando_retencion_origen,
                        on_change=OperacionesState.set_editando_retencion_origen,
                        width="100%",
                    ),
                ),
                campo(
                    "Retención destino (€)",
                    rx.input(
                        type="number",
                        value=OperacionesState.editando_retencion_destino,
                        on_change=OperacionesState.set_editando_retencion_destino,
                        width="100%",
                    ),
                ),
                campo_calculado(
                    "Importe neto (€)",
                    OperacionesState.editando_importe_neto,
                    nota="Solo informativo, no se guarda.",
                ),
                columns=rx.breakpoints(initial="1", md="3"),
                spacing="3",
                width="100%",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def campos_editar_segun_tipo() -> rx.Component:
    return rx.match(
        OperacionesState.editando_tipo_operacion,
        (("Compra", "Venta", "Prima"), campos_editar_compra_venta_prima()),
        ("Dividendo", campos_editar_dividendo()),
        ("Script", campos_editar_script()),
        campos_editar_compra_venta_prima(),
    )


def dialogo_confirmar_eliminar() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Eliminar operación"),
            rx.alert_dialog.description(
                "Esta acción no se puede deshacer. ¿Seguro que quieres eliminar esta operación?"
            ),
            rx.cond(
                OperacionesState.eliminar_error != "",
                rx.callout(OperacionesState.eliminar_error, color_scheme="red", size="1"),
            ),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button("Cancelar", variant="soft", color_scheme="gray", type="button")
                ),
                rx.button(
                    "Eliminar",
                    color_scheme="red",
                    type="button",
                    on_click=OperacionesState.eliminar_operacion_actual,
                ),
                spacing="3",
                justify="end",
                width="100%",
                padding_top=SPACE_SM,
            ),
            direction="column",
        ),
        open=OperacionesState.confirmar_eliminar_open,
        on_open_change=OperacionesState.set_confirmar_eliminar_open,
    )


def dialogo_editar_operacion() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.flex(
                rx.heading("Editar operación", size="4"),
                rx.grid(
                    campo(
                        "Tipo de operación",
                        rx.input(
                            value=OperacionesState.editando_tipo_operacion,
                            disabled=True,
                            width="100%",
                        ),
                    ),
                    campo(
                        "Valor",
                        rx.input(
                            value=OperacionesState.editando_ticker
                            + " — "
                            + OperacionesState.editando_empresa,
                            disabled=True,
                            width="100%",
                        ),
                    ),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="3",
                    width="100%",
                ),
                rx.text(
                    "El tipo de operación y el valor no se pueden cambiar aquí: elimina "
                    "esta operación y da de alta una nueva si te equivocaste en alguno "
                    "de los dos.",
                    size="1",
                    color_scheme="gray",
                ),
                rx.grid(
                    campo(
                        "Fecha",
                        rx.input(
                            type="date",
                            value=OperacionesState.editando_fecha,
                            on_change=OperacionesState.set_editando_fecha,
                            width="100%",
                        ),
                    ),
                    campo_editar_broker(),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="3",
                    width="100%",
                ),
                campos_editar_segun_tipo(),
                rx.cond(
                    OperacionesState.aviso_saldo_edicion != "",
                    rx.callout(
                        OperacionesState.aviso_saldo_edicion,
                        color_scheme=rx.cond(
                            OperacionesState.bloqueo_saldo_edicion, "red", "amber"
                        ),
                        size="1",
                    ),
                ),
                campo(
                    "Observaciones",
                    rx.text_area(
                        value=OperacionesState.editando_observaciones,
                        on_change=OperacionesState.set_editando_observaciones,
                        width="100%",
                    ),
                ),
                rx.cond(
                    OperacionesState.editar_error != "",
                    rx.callout(OperacionesState.editar_error, color_scheme="red", size="1"),
                ),
                rx.hstack(
                    rx.button(
                        "Eliminar operación",
                        color_scheme="red",
                        variant="soft",
                        type="button",
                        on_click=OperacionesState.abrir_confirmar_eliminar,
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button("Cancelar", variant="soft", color_scheme="gray", type="button")
                    ),
                    rx.button("Guardar cambios", on_click=OperacionesState.guardar_edicion),
                    spacing="3",
                    width="100%",
                    padding_top=SPACE_SM,
                ),
                dialogo_confirmar_eliminar(),
                direction="column",
                spacing="4",
            ),
            style={"maxWidth": "720px", "maxHeight": "85vh", "overflowY": "auto"},
        ),
        open=OperacionesState.editar_open,
        on_open_change=OperacionesState.set_editar_open,
    )


def dialogo_alta_operacion() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            alta_operacion_form(on_cancel=OperacionesState.cerrar_alta),
            style={"maxWidth": "760px", "maxHeight": "85vh", "overflowY": "auto"},
        ),
        open=OperacionesState.alta_open,
        on_open_change=OperacionesState.set_alta_open,
    )


def pagina_operaciones() -> rx.Component:
    return rx.container(
        header(extra_on_portfolio_change=[OperacionesState.cargar_datos]),
        rx.flex(
            page_title(
                "Operaciones",
                "Historial de compras, ventas, dividendos y demás movimientos.",
            ),
            rx.hstack(
                rx.button(
                    "Alta Operación",
                    on_click=[
                        OperacionesState.abrir_alta,
                        AltaOperacionState.cargar_datos_iniciales,
                    ],
                ),
                rx.spacer(),
                rx.input(
                    placeholder="Buscar por tipo, ticker, empresa o bróker…",
                    value=OperacionesState.busqueda,
                    on_change=OperacionesState.set_busqueda,
                    max_width="320px",
                    width="100%",
                ),
                width="100%",
                align="center",
                wrap="wrap",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        columna_ordenable("Tipo", "tipo_operacion"),
                        columna_ordenable("Fecha", "fecha"),
                        columna_ordenable("Ticker", "ticker"),
                        columna_ordenable("Empresa", "empresa"),
                        columna_ordenable("Nº títulos", "num_titulos"),
                        columna_ordenable("Bróker", "broker"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(OperacionesState.operaciones_filtradas, fila_operacion)
                ),
                width="100%",
                height="75vh",
                min_width="0",
            ),
            rx.cond(
                OperacionesState.operaciones_filtradas.length() == 0,
                rx.text(
                    "No hay operaciones que mostrar.",
                    color_scheme="gray",
                    size="2",
                    padding_y=SPACE_MD,
                ),
            ),
            dialogo_alta_operacion(),
            dialogo_editar_operacion(),
            direction="column",
            spacing="4",
            padding="1em",
        ),
        size="4",
    )


def operaciones() -> rx.Component:
    return requiere_login(pagina_operaciones())

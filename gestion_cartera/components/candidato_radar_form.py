"""Formulario de alta de un candidato en la lista de posibles compras
de RADAR (punto 4 del encargo) -- mismo buscador/alta de valor nuevo
que components/alta_operacion_form.py (Twelve Data + clasificación
sectorial), pero sin bróker/fecha/nº de títulos: aquí se pide el
importe a invertir (en euros), el precio de compra, opcional (umbral
que pinta la fila de ámbar/rojo y manda el aviso de compra, ver
radar_db._color_fila_candidato) y el precio de venta, opcional (solo
manda un aviso por SMS al alcanzarlo o superarlo, sin afectar al
color de la fila -- ver states/radar_candidato_state.py,
refrescar_cotizaciones). Los dos precios son independientes entre sí
y van en la divisa origen del valor.

Recibe el estado (`RadarCandidatoState` o `RadarCandidatoCortoPlazoState`
-- dos estados independientes que comparten toda su lógica mediante un
mixin, ver states/radar_candidato_state.py) como parámetro `state`,
para poder reutilizar el mismo formulario en las dos listas (Largo
Plazo y Corto Plazo, punto 7 del encargo) sin duplicar este fichero.
"""

import reflex as rx

from gestion_cartera.radar_db import SUPERSECTORES, ZONAS
from gestion_cartera.states.radar_candidato_state import RadarCandidatoState, _RadarCandidatoMixin


def _campo(label: str, *children) -> rx.Component:
    return rx.flex(
        rx.text(label, size="2", weight="medium", color_scheme="gray"),
        *children,
        direction="column",
        spacing="1",
        width="100%",
    )


def _resultado_valor_existente_item(item: dict, state: type[_RadarCandidatoMixin]) -> rx.Component:
    return rx.button(
        rx.hstack(
            rx.text(item["ticker"], weight="bold"),
            rx.text(item["empresa"]),
            rx.spacer(),
            rx.text(item["mercado"], size="1", color_scheme="gray"),
            width="100%",
        ),
        on_click=state.elegir_valor_existente(
            item["ticker"], item["mercado"], item["empresa"]
        ),
        variant="soft",
        width="100%",
        justify="start",
    )


def _resultado_busqueda_item(item: dict, state: type[_RadarCandidatoMixin]) -> rx.Component:
    return rx.button(
        rx.hstack(
            rx.text(item["ticker"], weight="bold"),
            rx.text(item["empresa"]),
            rx.spacer(),
            rx.text(item["bolsa"], size="1", color_scheme="gray"),
            width="100%",
        ),
        on_click=state.seleccionar_resultado_busqueda(
            item["ticker"], item["empresa"], item["moneda"], item["bolsa"]
        ),
        variant="soft",
        width="100%",
        justify="start",
    )


def _subformulario_nuevo_valor(state: type[_RadarCandidatoMixin]) -> rx.Component:
    return rx.flex(
        _campo(
            "Buscar valor (ticker o nombre)",
            rx.input(
                placeholder="Ej: Inditex, ITX...",
                value=state.busqueda_texto,
                on_change=[
                    state.set_busqueda_texto,
                    state.buscar_valor.debounce(400),
                ],
                width="100%",
            ),
        ),
        rx.cond(
            state.busqueda_error != "",
            rx.callout(state.busqueda_error, color_scheme="red", size="1"),
        ),
        rx.cond(
            state.busqueda_texto != "",
            rx.flex(
                rx.foreach(
                    state.resultados_busqueda,
                    lambda item: _resultado_busqueda_item(item, state),
                ),
                direction="column",
                spacing="1",
            ),
        ),
        rx.cond(
            state.ticker_nuevo != "",
            rx.flex(
                rx.callout(
                    rx.text(
                        "Seleccionado: ",
                        state.ticker_nuevo,
                        " — ",
                        state.empresa_nueva,
                        " (",
                        state.moneda_nueva,
                        ") · ",
                        state.mercado_nuevo,
                    ),
                    color_scheme="blue",
                    size="1",
                ),
                rx.cond(
                    state.advertencia_ticker != "",
                    rx.flex(
                        rx.callout(
                            state.advertencia_ticker,
                            color_scheme=rx.cond(
                                state.requiere_confirmacion_mercado,
                                "amber",
                                "red",
                            ),
                            size="1",
                        ),
                        rx.cond(
                            state.requiere_confirmacion_mercado,
                            rx.text(
                                rx.checkbox(
                                    checked=state.confirmar_mercado_distinto,
                                    on_change=state.set_confirmar_mercado_distinto,
                                ),
                                " Confirmo que es un valor distinto (mercado diferente).",
                                as_="label",
                                size="2",
                            ),
                        ),
                        direction="column",
                        spacing="2",
                    ),
                ),
                _campo(
                    "Zona",
                    rx.select(
                        ZONAS,
                        placeholder="Elige zona",
                        value=state.zona_nueva,
                        on_change=state.set_zona_nueva,
                        width="100%",
                    ),
                ),
                rx.grid(
                    _campo(
                        "Supersector",
                        rx.select(
                            SUPERSECTORES,
                            placeholder="Elige supersector",
                            value=state.supersector_nuevo,
                            on_change=state.set_supersector_nuevo,
                            width="100%",
                        ),
                    ),
                    _campo(
                        "Sector",
                        rx.select(
                            state.sectores_disponibles,
                            placeholder="Elige sector",
                            value=state.sector_nuevo,
                            on_change=state.set_sector_nuevo,
                            disabled=state.supersector_nuevo == "",
                            key=state.supersector_nuevo,
                            width="100%",
                        ),
                    ),
                    _campo(
                        "Industria",
                        rx.select(
                            state.industrias_disponibles,
                            placeholder="Elige industria",
                            value=state.industria_nueva,
                            on_change=state.set_industria_nueva,
                            disabled=state.sector_nuevo == "",
                            key=state.supersector_nuevo + "|" + state.sector_nuevo,
                            width="100%",
                        ),
                    ),
                    columns=rx.breakpoints(initial="1", md="3"),
                    spacing="3",
                    width="100%",
                ),
                direction="column",
                spacing="3",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def _subformulario_valor_existente(state: type[_RadarCandidatoMixin]) -> rx.Component:
    return rx.flex(
        _campo(
            "Buscar en tu catálogo (ticker o nombre)",
            rx.input(
                placeholder="Ej: Inditex, ITX...",
                value=state.busqueda_valor_existente,
                on_change=state.set_busqueda_valor_existente,
                width="100%",
            ),
        ),
        rx.cond(
            state.valor_existente != "",
            rx.callout(
                f"Seleccionado: {state.valor_existente}",
                color_scheme="blue",
                size="1",
            ),
        ),
        rx.cond(
            state.busqueda_valor_existente != "",
            rx.flex(
                rx.foreach(
                    state.resultados_valor_existente,
                    lambda item: _resultado_valor_existente_item(item, state),
                ),
                direction="column",
                spacing="1",
            ),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def formulario_candidato(state: type[_RadarCandidatoMixin] = RadarCandidatoState) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading("Añadir a la lista", size="3"),
            rx.segmented_control.root(
                rx.segmented_control.item("Valor existente", value="existente"),
                rx.segmented_control.item("Dar de alta uno nuevo", value="nuevo"),
                value=state.modo_valor,
                on_change=state.set_modo_valor,
            ),
            rx.cond(
                state.modo_valor == "existente",
                _subformulario_valor_existente(state),
                _subformulario_nuevo_valor(state),
            ),
            rx.grid(
                _campo(
                    "Importe a invertir (€)",
                    rx.input(
                        type="number",
                        value=state.importe_invertir,
                        on_change=state.set_importe_invertir,
                        width="100%",
                    ),
                ),
                _campo(
                    "Precio de compra (divisa origen, opcional)",
                    rx.input(
                        type="number",
                        value=state.precio_max,
                        on_change=state.set_precio_max,
                        width="100%",
                    ),
                ),
                _campo(
                    "Precio de venta (divisa origen, opcional)",
                    rx.input(
                        type="number",
                        value=state.precio_min,
                        on_change=state.set_precio_min,
                        width="100%",
                    ),
                ),
                columns=rx.breakpoints(initial="1", md="3"),
                spacing="3",
                width="100%",
            ),
            rx.cond(
                state.guardado_error != "",
                rx.callout(state.guardado_error, color_scheme="red", size="1"),
            ),
            rx.hstack(
                rx.button(
                    "Cancelar", variant="soft", color_scheme="gray",
                    on_click=state.cancelar_formulario,
                ),
                rx.spacer(),
                rx.button("Guardar", on_click=state.guardar_candidato),
                width="100%",
            ),
            direction="column",
            spacing="3",
        ),
        variant="surface",
        width="100%",
    )

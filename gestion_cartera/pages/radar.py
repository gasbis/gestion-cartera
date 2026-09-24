"""Página RADAR (/radar). Trabaja SIEMPRE sobre la cartera de Largo
Plazo (ver radar_db.py), así que -- a diferencia de
Inicio/Cartera/Operaciones -- no lleva el selector de cartera del
header, sino la etiqueta fija "Cartera de largo plazo" (ver
components/header.py, parámetro `etiqueta_fija`).

Fase 1 (puntos 1-3): objetivo de balance (peso deseado por supersector
y por zona, editable y persistente) frente al peso ACTUAL de la
cartera.

Fase 2 (punto 4, este añadido): lista de posibles compras, con color
de aviso según lo cerca que esté la cotización del precio de compra
marcado (ver radar_db._color_fila_candidato) y refresco de
cotizaciones. El precio de venta (opcional) no afecta al color: solo
dispara un aviso por SMS al alcanzarse o superarse (punto 5, ver
states/radar_candidato_state.py, refrescar_cotizaciones).

Fase 3 (punto 6): gráficos de objetivo vs. real aplicando las compras
listadas (Largo Plazo), con barra apilada Actual + Cambio proyectado.

Fase 4 (punto 7, este añadido): segunda lista de posibles compras,
"Corto Plazo" -- misma tabla/formulario que la de Largo Plazo (ver
_lista_candidatos, ahora parametrizada por `state` para poder
reutilizarla con RadarCandidatoState o con RadarCandidatoCortoPlazoState,
dos estados independientes que comparten lógica mediante un mixin, ver
states/radar_candidato_state.py), pero sin efecto en los gráficos de
balance/reequilibrio de arriba (ACTUALIZA_PROYECCION en ese mismo
fichero).

Fase 5 (punto 5 del encargo): avisos por SMS (Twilio), ver
states/radar_candidato_state.py (refrescar_cotizaciones) y
services/twilio_sms.py.
"""

import reflex as rx

from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.candidato_radar_form import formulario_candidato
from gestion_cartera.components.header import header
from gestion_cartera.components.page_title import page_title
from gestion_cartera.components.scroll_x import scroll_x
from gestion_cartera.radar_db import SUPERSECTORES, ZONAS
from gestion_cartera.states.radar_candidato_state import (
    RadarCandidatoCortoPlazoState,
    RadarCandidatoState,
    _RadarCandidatoMixin,
)
from gestion_cartera.states.radar_state import RadarState
from gestion_cartera.styles import SPACE_SM


def _fila_peso(categoria: str, pesos: rx.Var, on_change) -> rx.Component:
    return rx.flex(
        rx.text(categoria, size="2", width="7em", flex_shrink="0"),
        rx.input(
            type="number",
            min=0,
            max=100,
            value=pesos[categoria],
            on_change=on_change(categoria),
            width="6em",
        ),
        rx.text("%", size="2", color_scheme="gray"),
        align="center",
        spacing="2",
    )


def _bloque_objetivo(
    titulo: str,
    categorias: list[str],
    pesos: rx.Var,
    suma: rx.Var,
    on_change,
    on_guardar,
    guardado: rx.Var,
) -> rx.Component:
    """`height="100%"` en la card y en el flex + un `rx.spacer()` antes
    de la fila de Guardar: así, cuando esta card queda más alta que su
    vecina (p.ej. Supersectores con 3 categorías junto a Zona con 4),
    el hueco sobrante se reparte ANTES del botón y la fila
    Suma/Guardar queda siempre pegada abajo, en vez de dejar un hueco
    en blanco debajo."""
    suma_ok = suma == 100
    return rx.card(
        rx.flex(
            rx.heading(f"Objetivo · {titulo}", size="3"),
            rx.text(
                "Reparte 100 puntos entre las categorías según el peso que quieras que tengan "
                "en la cartera.",
                size="1",
                color_scheme="gray",
            ),
            *[_fila_peso(c, pesos, on_change) for c in categorias],
            rx.spacer(),
            rx.flex(
                rx.text(
                    rx.cond(suma_ok, f"Suma: {suma} / 100 ✓", f"Suma: {suma} / 100"),
                    size="2",
                    weight="medium",
                    color=rx.cond(suma_ok, "var(--green-9)", "var(--red-9)"),
                ),
                rx.spacer(),
                rx.button("Guardar", size="2", disabled=suma != 100, on_click=on_guardar),
                align="center",
                width="100%",
            ),
            rx.cond(
                guardado,
                rx.text("Objetivo guardado.", size="1", color="var(--green-9)"),
            ),
            direction="column",
            spacing="3",
            height="100%",
        ),
        width="100%",
        height="100%",
    )


def _leyenda_item(color, label: str) -> rx.Component:
    return rx.hstack(
        rx.box(width="10px", height="10px", border_radius="2px", background_color=color, flex_shrink="0"),
        rx.text(label, size="1", color_scheme="gray"),
        spacing="1",
        align="center",
    )


def _leyenda(*items: tuple) -> rx.Component:
    """Leyenda propia (no la de recharts): recharts la dibuja DENTRO
    del SVG del gráfico, así que su posición depende de la altura fija
    de ESE gráfico -- no se puede desacoplar de él con un spacer. Al
    dibujarla nosotros, fuera del gráfico, sí queda libre para fijarla
    siempre abajo de la card (ver _bloque_comparado/_bloque_proyeccion)
    mientras el gráfico en sí queda pegado arriba, justo debajo del
    título."""
    return rx.hstack(
        *[_leyenda_item(color, label) for color, label in items],
        spacing="4",
        wrap="wrap",
        justify="center",
        width="100%",
    )


def _grafico_objetivo_comparado(data: rx.Var, campo: str, nombre_serie: str) -> rx.Component:
    """Barras horizontales agrupadas, mismo patrón visual que las de
    Inicio (ver pages/index.py, distribucion_chart): una barra Objetivo
    y una barra `nombre_serie` por categoría, con el % ya escrito
    encima. `campo` es el prefijo de las claves del segundo valor
    ("actual" o "proyectado", ver states/radar_state._datos_grafico).
    Sin leyenda propia -- la pone _bloque_comparado por fuera, ver
    _leyenda."""
    altura = data.length() * 70 + 20
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key="objetivo_pct_mostrar", position="right", fill=rx.color("gray", 11)
            ),
            data_key="objetivo_pct",
            name="Objetivo",
            fill=rx.color("accent", 5),
            radius=[0, 4, 4, 0],
        ),
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key=f"{campo}_pct_mostrar", position="right", fill=rx.color("gray", 11)
            ),
            data_key=f"{campo}_pct",
            name=nombre_serie,
            fill=rx.color("accent", 9),
            radius=[0, 4, 4, 0],
        ),
        rx.recharts.x_axis(type_="number", hide=True),
        rx.recharts.y_axis(data_key="name", type_="category", axis_line=False, tick_line=False, width=90),
        data=data,
        layout="vertical",
        margin={"right": 40},
        width="100%",
        height=altura,
    )


def _bloque_comparado(titulo_serie: str, titulo: str, data: rx.Var, campo: str) -> rx.Component:
    """El gráfico va justo debajo del título (alineado arriba, misma
    posición en todas las cards de la fila); el `rx.spacer()` va
    DESPUÉS, así que es la leyenda la que se empuja hacia abajo y
    queda siempre pegada al borde inferior de la card, aunque la
    vecina en la misma fila sea más alta (p.ej. Supersectores con 3
    categorías junto a Zona con 4)."""
    return rx.card(
        rx.flex(
            rx.heading(f"{titulo_serie} · {titulo}", size="3"),
            _grafico_objetivo_comparado(data, campo, titulo_serie),
            rx.spacer(),
            _leyenda(
                (rx.color("accent", 5), "Objetivo"),
                (rx.color("accent", 9), titulo_serie),
            ),
            direction="column",
            spacing="3",
            height="100%",
        ),
        width="100%",
        height="100%",
    )


def _grafico_proyeccion(data: rx.Var) -> rx.Component:
    """Barra "Objetivo" de referencia + barra apilada Actual (color
    neutro, longitud real, sin etiqueta propia) + Cambio proyectado
    (verde si el cambio acerca al objetivo, rojo si lo aleja -- ver
    states/radar_state._datos_grafico_proyeccion). El segundo tramo usa
    un <Cell> por fila para poder pintar cada categoría de un color
    distinto dentro de la misma serie.

    Una sola etiqueta por fila (Actual + cambio juntos,
    `resumen_cambio_mostrar`), colgada del tramo de Cambio -- con una
    etiqueta en cada tramo se solapaban en las barras cortas, sobre
    todo cuando el cambio es pequeño o negativo. Sin leyenda propia
    (la pone _bloque_proyeccion por fuera, ver _leyenda) y sin el
    tramo de Cambio en ella -- no tiene un único color fijo (es verde o
    rojo según la fila) y la explicación ya está en el texto de encima
    del gráfico, así que no aporta como entrada de leyenda."""
    altura = data.length() * 70 + 20
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key="objetivo_pct_mostrar", position="right", fill=rx.color("gray", 11)
            ),
            data_key="objetivo_pct",
            name="Objetivo",
            fill=rx.color("accent", 5),
            radius=[0, 4, 4, 0],
        ),
        rx.recharts.bar(
            data_key="actual_pct",
            name="Actual",
            stack_id="proyeccion",
            fill=rx.color("gray", 8),
        ),
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key="resumen_cambio_mostrar", position="right", fill=rx.color("gray", 11)
            ),
            rx.foreach(data, lambda item: rx.recharts.cell(fill=item["color_cambio"])),
            data_key="cambio_pct",
            name="Cambio proyectado",
            stack_id="proyeccion",
            radius=[0, 4, 4, 0],
        ),
        rx.recharts.x_axis(type_="number", hide=True),
        rx.recharts.y_axis(data_key="name", type_="category", axis_line=False, tick_line=False, width=90),
        data=data,
        layout="vertical",
        margin={"right": 60},
        width="100%",
        height=altura,
    )


def _bloque_proyeccion(titulo: str, data: rx.Var) -> rx.Component:
    """Mismo motivo que _bloque_comparado: el gráfico queda arriba,
    pegado al título, y el spacer empuja la leyenda hacia el borde
    inferior de la card aunque la vecina de fila sea más alta. Sin
    entrada de Cambio en la leyenda -- ver _grafico_proyeccion."""
    return rx.card(
        rx.flex(
            rx.heading(titulo, size="3"),
            _grafico_proyeccion(data),
            rx.spacer(),
            _leyenda(
                (rx.color("accent", 5), "Objetivo"),
                (rx.color("gray", 8), "Actual"),
            ),
            direction="column",
            spacing="3",
            height="100%",
        ),
        width="100%",
        height="100%",
    )


def _fila_candidato_edicion(item: dict, state: type[_RadarCandidatoMixin]) -> rx.Component:
    """Fila en modo edición: los tres importes se cambian por inputs;
    el resto de columnas (ticker, empresa...) se quedan solo de
    lectura -- para cambiarlas hay que borrar la fila y añadirla de
    nuevo."""
    return rx.fragment(
        rx.table.row(
            rx.table.cell(item["ticker"], weight="medium"),
            rx.table.cell(item["empresa"]),
            rx.table.cell(item["zona"]),
            rx.table.cell(item["supersector"]),
            rx.table.cell(item["sector"]),
            rx.table.cell(item["grupo"]),
            rx.table.cell(
                rx.input(
                    type="number",
                    value=state.editando_importe,
                    on_change=state.set_editando_importe,
                    width="8em",
                )
            ),
            rx.table.cell(
                rx.input(
                    type="number",
                    value=state.editando_precio_max,
                    on_change=state.set_editando_precio_max,
                    width="8em",
                )
            ),
            rx.table.cell(
                rx.input(
                    type="number",
                    value=state.editando_precio_min,
                    on_change=state.set_editando_precio_min,
                    width="8em",
                )
            ),
            rx.table.cell(item["cotizacion_divisa_mostrar"], title=item["cotizacion_eur_mostrar"]),
            rx.table.cell(
                rx.hstack(
                    rx.icon_button(
                        rx.icon(tag="check", size=16),
                        size="1",
                        variant="soft",
                        color_scheme="green",
                        on_click=state.guardar_edicion,
                    ),
                    rx.icon_button(
                        rx.icon(tag="x", size=16),
                        size="1",
                        variant="soft",
                        color_scheme="gray",
                        on_click=state.cancelar_edicion,
                    ),
                    spacing="1",
                )
            ),
            background_color=rx.match(item["color_fila"], ("red", "var(--red-a3)"), ("amber", "var(--amber-a3)"), "transparent"),
        ),
        rx.cond(
            state.editando_error != "",
            rx.table.row(
                rx.table.cell(
                    rx.callout(state.editando_error, color_scheme="red", size="1"),
                    col_span=11,
                ),
            ),
        ),
    )


def _fila_candidato_lectura(item: dict, state: type[_RadarCandidatoMixin]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["ticker"], weight="medium"),
        rx.table.cell(item["empresa"]),
        rx.table.cell(item["zona"]),
        rx.table.cell(item["supersector"]),
        rx.table.cell(item["sector"]),
        rx.table.cell(item["grupo"]),
        rx.table.cell(item["importe_invertir_mostrar"], text_align="right"),
        rx.table.cell(item["precio_max_mostrar"], text_align="right"),
        rx.table.cell(item["precio_min_mostrar"], text_align="right"),
        rx.table.cell(
            item["cotizacion_divisa_mostrar"],
            title=item["cotizacion_eur_mostrar"],
            text_align="right",
        ),
        rx.table.cell(
            rx.hstack(
                rx.icon_button(
                    rx.icon(tag="pencil", size=16),
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=state.empezar_edicion(
                        item["id"],
                        item["importe_invertir_str"],
                        item["precio_max_str"],
                        item["precio_min_str"],
                    ),
                ),
                rx.icon_button(
                    rx.icon(tag="trash", size=16),
                    size="1",
                    variant="soft",
                    color_scheme="red",
                    on_click=state.eliminar(item["id"]),
                ),
                spacing="1",
            )
        ),
        background_color=rx.match(item["color_fila"], ("red", "var(--red-a3)"), ("amber", "var(--amber-a3)"), "transparent"),
    )


def _fila_candidato(item: dict, state: type[_RadarCandidatoMixin]) -> rx.Component:
    return rx.cond(
        state.editando_id == item["id"],
        _fila_candidato_edicion(item, state),
        _fila_candidato_lectura(item, state),
    )


def _lista_candidatos(
    titulo: str,
    state: type[_RadarCandidatoMixin],
    texto_vacio: str = "Todavía no hay ningún valor en seguimiento.",
) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.flex(
                rx.heading(titulo, size="3"),
                rx.spacer(),
                rx.cond(
                    state.actualizando_cotizaciones,
                    rx.text("Actualizando cotizaciones…", size="1", color_scheme="gray"),
                ),
                rx.button(
                    rx.icon(tag="plus", size=16),
                    "Añadir",
                    size="2",
                    variant="soft",
                    on_click=state.abrir_formulario,
                ),
                align="center",
                width="100%",
                wrap="wrap",
                gap="0.5em",
            ),
            rx.text(
                "La cotización se muestra en la divisa origen del valor; pasa el ratón por "
                "encima para ver el equivalente en euros. Fila en rojo: la cotización ya está "
                "en el precio de compra o por debajo (manda aviso por SMS). Ámbar: está "
                "hasta un 10% por encima. El precio de venta no cambia el color: solo manda un "
                "aviso por SMS al alcanzarlo o superarlo.",
                size="1",
                color_scheme="gray",
            ),
            rx.cond(
                state.cotizaciones_error != "",
                rx.callout(state.cotizaciones_error, color_scheme="amber", size="1"),
            ),
            rx.cond(state.mostrar_formulario, formulario_candidato(state)),
            rx.cond(
                state.candidatos.length() > 0,
                scroll_x(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Ticker"),
                                rx.table.column_header_cell("Empresa"),
                                rx.table.column_header_cell("Zona"),
                                rx.table.column_header_cell("Supersector"),
                                rx.table.column_header_cell("Sector"),
                                rx.table.column_header_cell("Industria"),
                                rx.table.column_header_cell("Importe a invertir", text_align="right"),
                                rx.table.column_header_cell("Precio de compra", text_align="right"),
                                rx.table.column_header_cell("Precio de venta", text_align="right"),
                                rx.table.column_header_cell("Cotización", text_align="right"),
                                rx.table.column_header_cell(""),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(state.candidatos, lambda item: _fila_candidato(item, state))
                        ),
                        width="100%",
                    ),
                ),
                rx.text(texto_vacio, size="2", color_scheme="gray"),
            ),
            direction="column",
            spacing="3",
        ),
        width="100%",
    )


def pagina_radar() -> rx.Component:
    return rx.container(
        header(etiqueta_fija="Cartera de largo plazo"),
        rx.flex(
            page_title(
                "Radar",
                "Objetivo de balance por supersector y por zona, frente al peso actual de la "
                "cartera de Largo Plazo.",
            ),
            rx.grid(
                _bloque_objetivo(
                    "Supersectores",
                    SUPERSECTORES,
                    RadarState.objetivo_supersector,
                    RadarState.suma_objetivo_supersector,
                    RadarState.set_objetivo_supersector,
                    RadarState.guardar_supersector,
                    RadarState.guardado_supersector,
                ),
                _bloque_objetivo(
                    "Zona",
                    ZONAS,
                    RadarState.objetivo_zona,
                    RadarState.suma_objetivo_zona,
                    RadarState.set_objetivo_zona,
                    RadarState.guardar_zona,
                    RadarState.guardado_zona,
                ),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="4",
                width="100%",
            ),
            rx.grid(
                _bloque_comparado(
                    "Actual", "Supersectores", RadarState.datos_grafico_supersector, "actual"
                ),
                _bloque_comparado("Actual", "Zona", RadarState.datos_grafico_zona, "actual"),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="4",
                width="100%",
            ),
            _lista_candidatos("Lista de posibles compras · Largo Plazo", RadarCandidatoState),
            rx.flex(
                rx.heading("Objetivo vs. real aplicando las compras listadas", size="4"),
                rx.text(
                    "Cada barra: el Objetivo de referencia, y debajo el peso Actual (gris) con "
                    "el cambio que introducirían las compras proyectadas apilado a continuación "
                    "-- en verde si acerca esa categoría al objetivo, en rojo si la aleja.",
                    size="1",
                    color_scheme="gray",
                ),
                direction="column",
                spacing="1",
            ),
            rx.grid(
                _bloque_proyeccion("Supersectores", RadarState.datos_grafico_proyeccion_supersector),
                _bloque_proyeccion("Zona", RadarState.datos_grafico_proyeccion_zona),
                columns=rx.breakpoints(initial="1", sm="2"),
                spacing="4",
                width="100%",
            ),
            rx.flex(
                rx.heading("Corto Plazo", size="4"),
                rx.text(
                    "Lista aparte de posibles compras a corto plazo: no afecta al objetivo de "
                    "balance ni a los gráficos de arriba, solo sirve para hacer seguimiento de "
                    "su cotización.",
                    size="1",
                    color_scheme="gray",
                ),
                direction="column",
                spacing="1",
            ),
            _lista_candidatos(
                "Lista de posibles compras · Corto Plazo",
                RadarCandidatoCortoPlazoState,
                texto_vacio="Todavía no hay ningún valor en seguimiento a corto plazo.",
            ),
            direction="column",
            spacing="6",
            padding="1em",
            padding_top=SPACE_SM,
        ),
        size="4",
    )


def radar() -> rx.Component:
    return requiere_login(pagina_radar())

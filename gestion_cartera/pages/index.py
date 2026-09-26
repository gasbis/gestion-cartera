import reflex as rx
from gestion_cartera.components.header import header
from gestion_cartera.components.auth_guard import requiere_login
from gestion_cartera.components.page_title import page_title
from gestion_cartera.components.stat_card import stat_card
from gestion_cartera.states.index_state import ResumenGeneralState
from gestion_cartera.styles import SPACE_MD

from rxconfig import config


def summary_section() -> rx.Component:
    r = ResumenGeneralState.resumen
    return rx.grid(
        stat_card(
            "Valor de compra", r["valor_compra_mostrar"], "Suma de las compras-ventas."
        ),
        stat_card(
            "Valor actual",
            r["valor_mercado_mostrar"],
            "Valoración de la cartera con la cotización actual.",
        ),
        stat_card(
            "Saldo",
            r["saldo_eur_mostrar"],
            "Diferencia entre el valor de compra y el valor actual.",
            value_color=r["color_saldo"],
            secondary=r["saldo_pct_mostrar"],
        ),
        stat_card(
            "T.I.R.",
            r["tir_con_mostrar"],
            "Rentabilidad anual con / sin revalorización.",
            value_color=r["color_tir"],
            secondary=r["tir_sin_mostrar"],
        ),
        stat_card(
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
            height="100%",
        ),
        width="100%",
        height="100%",
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


def area_dividendos(data) -> rx.Component:
    """Gráfico de área (no de barras) para los dividendos por año.

    Con barras + etiqueta fija encima de cada una, cada año que pasa añade
    una barra más y, tarde o temprano, las cifras contiguas se solapan en
    pantalla estrecha (ya pasaba con una cartera de solo 10 años). Un
    gráfico de área no tiene ese problema: no hay texto fijo dibujado
    sobre el gráfico, la cifra de cada año se lee con el tooltip al pasar
    el ratón (o al tocar, en móvil) -- el mismo patrón que ya usan los
    gráficos de cotización de valor_detalle, con el que comparte estilo.
    """
    return rx.recharts.area_chart(
        rx.recharts.cartesian_grid(
            stroke_dasharray="3 3", vertical=False, stroke="var(--app-separator)"
        ),
        rx.recharts.x_axis(
            data_key="name",
            stroke="var(--gray-9)",
            tick_line=False,
            axis_line=False,
        ),
        rx.recharts.y_axis(
            stroke="var(--gray-9)",
            tick_line=False,
            axis_line=False,
            width=56,
        ),
        rx.recharts.graphing_tooltip(),
        rx.recharts.area(
            data_key="uv",
            name="Dividendos (€)",
            type_="monotone",
            stroke=rx.color("accent", 9),
            stroke_width=2,
            fill="var(--accent-a3)",
            dot={"r": 3},
            active_dot={"r": 5},
        ),
        data=data,
        margin={"top": 8, "right": 12, "left": 0, "bottom": 0},
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
                area_dividendos(data),
                rx.text("Sin dividendos registrados todavía.", size="2", color_scheme="gray"),
            ),
            direction="column",
            spacing="2",
        ),
        width="100%",
    )


def _leyenda_item(color, label: str) -> rx.Component:
    return rx.hstack(
        rx.box(width="10px", height="10px", border_radius="2px", background_color=color, flex_shrink="0"),
        rx.text(label, size="1", color_scheme="gray"),
        spacing="1",
        align="center",
    )


def _leyenda(*items: tuple) -> rx.Component:
    """Leyenda propia (no la de recharts, ver pages/radar.py para el
    porqué): así el gráfico queda pegado arriba, justo debajo del
    título, y la leyenda -- fuera del SVG -- queda libre para fijarse
    siempre abajo de la card con un spacer, aunque la card vecina en
    la misma fila (Zonas/Sectores) sea más alta."""
    return rx.hstack(
        *[_leyenda_item(color, label) for color, label in items],
        spacing="4",
        wrap="wrap",
        justify="center",
        width="100%",
    )


def distribucion_chart(data) -> rx.Component:
    """Barras horizontales agrupadas: dos barras por zona/sector (valor
    de compra vs. valor actual), mismo tono en dos intensidades (antes /
    después), con el % ya escrito en la propia barra -- así se compara
    de un vistazo cómo ha cambiado el peso de cada grupo sin tener que
    pasar el ratón por encima ni comparar ángulos de un donut. Sin
    leyenda propia -- la pone distribucion_section por fuera, ver
    _leyenda. `width=90` en el eje Y: con 70 se cortaba por la
    izquierda la etiqueta "Defensivo" (el nombre de supersector más
    largo) al no caber en el ancho reservado para el texto."""
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
        rx.recharts.y_axis(data_key="name", type_="category", axis_line=False, tick_line=False, width=90),
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
                rx.fragment(
                    distribucion_chart(data),
                    rx.spacer(),
                    _leyenda(
                        (rx.color("accent", 5), "Valor de compra"),
                        (rx.color("accent", 9), "Valor actual"),
                    ),
                ),
                rx.text("Sin datos todavía.", size="2", color_scheme="gray"),
            ),
            direction="column",
            spacing="2",
            height="100%",
        ),
        width="100%",
        height="100%",
    )


# Paleta categórica del donut de Sectores: 5 tonos fijos (identidad de
# cada sector) + gris para "Otros" (el cajón de sastre de los sectores
# más pequeños no es una identidad, así que no le corresponde un tono
# categórico -- ver `_distribucion_pie` en resumen_db.py). Los 5 tonos
# son los 5 primeros de la paleta categórica de referencia validada con
# el skill de dataviz (`validate_palette.js`) contra el fondo oscuro de
# esta app (`--color-panel-solid: #1a1a1a`, prácticamente igual al
# `#1a1a19` de referencia): ΔE CVD adyacente 8.4 y ΔE visión normal
# adyacente 19.3, ambos por encima del umbral. Los sectores se colorean
# por orden de peso (mayor a menor, tal como ya vienen ordenados desde
# el backend) y no por nombre fijo: con como mucho 6 franjas visibles a
# la vez (5 + Otros) el orden ya evita que dos sectores compartan tono
# en una misma vista.
# Envuelto en un Var (no una lista Python a secas): dentro de
# `rx.foreach` el índice `i` es un Var, y una lista Python normal no se
# puede indexar con un Var (TypeError en tiempo de compilación) -- un
# Var-lista sí sabe generar el acceso `colores[i]` en el JS resultante.
_SECTOR_PIE_COLORES = rx.Var.create(
    [
        "#3987e5",  # azul
        "#d95926",  # naranja
        "#199e70",  # aqua
        "#c98500",  # amarillo
        "#d55181",  # magenta
        "var(--gray-9)",  # Otros
    ]
)


def _leyenda_item_sector(item: dict, color: str) -> rx.Component:
    fila = rx.hstack(
        rx.box(width="10px", height="10px", border_radius="2px", background_color=color, flex_shrink="0"),
        rx.text(item["name"], size="1", color_scheme="gray"),
        rx.text(item["valor_pct_mostrar"], size="1", weight="medium"),
        spacing="1",
        align="center",
    )
    # "Otros" trae su desglose ya preparado desde el backend
    # (`detalle_mostrar`, ver `_distribucion_pie`) -- un % agregado sin
    # más no dice nada por sí solo, así que aquí se enseña al pasar el
    # ratón (o al tocar, en móvil) en vez de sumar más franjas al donut.
    return rx.cond(
        item["detalle_mostrar"] != "",
        rx.tooltip(
            rx.hstack(fila, rx.icon("info", size=11, color=rx.color("gray", 9)), spacing="1", align="center"),
            content=item["detalle_mostrar"].to(str),
        ),
        fila,
    )


def _leyenda_sectores(data) -> rx.Component:
    """Leyenda propia (no la de recharts, mismo motivo que `_leyenda`)
    con el nombre y el % de cada sector ya escritos -- el donut, en
    fondo oscuro, tiene algún tono (amarillo, aqua, magenta) por debajo
    del contraste 3:1 recomendado para texto/marca fina, así que estos
    valores visibles junto al color hacen de refuerzo en vez de
    depender solo del tono para distinguir sectores."""
    return rx.flex(
        rx.foreach(
            data,
            lambda item, i: _leyenda_item_sector(item, _SECTOR_PIE_COLORES[i]),
        ),
        spacing="4",
        wrap="wrap",
        justify="center",
        width="100%",
    )


def donut_sectores_chart(data) -> rx.Component:
    """Donut con la composición ACTUAL de la cartera por sector
    Morningstar (más granular que el supersector de la card
    "Supersectores" de arriba, que compara compra vs. actual con
    barras). Aquí solo hace falta una magnitud -- el peso actual -- así
    que sí tiene sentido un donut en vez de barras; capado a 5 sectores
    + "Otros" en el backend (`_distribucion_pie`) para no superar los
    ~6 segmentos que un donut se puede leer de un vistazo. `padding_angle`
    y el `stroke` del color de fondo de la card separan visualmente las
    franjas (el mismo hueco de 2px entre marcas que ya usan las barras
    de distribución, aplicado aquí como anillo en vez de espacio)."""
    return rx.recharts.pie_chart(
        rx.recharts.graphing_tooltip(),
        rx.recharts.pie(
            rx.foreach(
                data,
                lambda item, i: rx.recharts.cell(fill=_SECTOR_PIE_COLORES[i]),
            ),
            data=data,
            data_key="valor_pct",
            name_key="name",
            cx="50%",
            cy="50%",
            inner_radius="55%",
            outer_radius="85%",
            padding_angle=2,
            stroke="var(--color-panel-solid)",
            stroke_width=2,
        ),
        width="100%",
        height=260,
    )


def donut_sectores_section() -> rx.Component:
    data = ResumenGeneralState.sectores_pie
    return rx.card(
        rx.flex(
            rx.heading("Sectores -valor actual-", size="3"),
            rx.cond(
                data.length() > 0,
                rx.fragment(
                    donut_sectores_chart(data),
                    rx.spacer(),
                    _leyenda_sectores(data),
                ),
                rx.text("Sin datos todavía.", size="2", color_scheme="gray"),
            ),
            direction="column",
            spacing="2",
            align="center",
        ),
        width="100%",
    )


def index() -> rx.Component:
    return requiere_login(
        rx.container(
            header(
                extra_on_portfolio_change=[ResumenGeneralState.cargar_datos],
                mostrar_selector_cartera=True,
            ),
            rx.stack(
                page_title("Inicio", "Visión general del estado de tu cartera de valores."),
                rx.skeleton(summary_section(), loading=ResumenGeneralState.cargando),
                rx.skeleton(tables_section(), loading=ResumenGeneralState.cargando),
                rx.skeleton(
                    chart_section(
                        "Dividendos",
                        ResumenGeneralState.dividendos_por_anio,
                        total=ResumenGeneralState.dividendos_totales_mostrar,
                    ),
                    loading=ResumenGeneralState.cargando,
                ),
                rx.skeleton(
                    rx.grid(
                        distribucion_section("Zonas", ResumenGeneralState.zonas),
                        # Antes se llamaba "Sectores" a secas, pero agrupa
                        # por SUPERsector (Cíclico/Defensivo/Sensible, solo
                        # 3 grupos) -- se renombra aquí para no chocar con
                        # el donut de más abajo, que sí es por sector
                        # (Morningstar, 11 posibles) y se queda con el
                        # nombre correcto.
                        distribucion_section("Supersectores", ResumenGeneralState.sectores),
                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="4",
                        width="100%",
                    ),
                    loading=ResumenGeneralState.cargando,
                ),
                rx.skeleton(
                    donut_sectores_section(),
                    loading=ResumenGeneralState.cargando,
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

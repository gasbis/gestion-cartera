"""Formulario de alta de operación, con sub-formulario de alta de valor nuevo.

Los campos visibles cambian según el tipo de operación:
- Compra / Venta / Prima: NumTits, Importe, Importe unitario (calculado),
  Observaciones. Solo "Compra" permite dar de alta un valor nuevo.
- Dividendo: NumTits, Importe, Importe unitario (calculado), Observaciones,
  Retención origen/destino, Importe neto (calculado, solo informativo, NO
  se guarda).
- Script: Tipo de derecho (compra/venta), Nº títulos recibidos (se guarda
  en NumTits), Importe (según tipo de derecho), Retención origen/destino,
  Importe neto (calculado, solo informativo, NO se guarda).

Todo lo marcado como "MOCK" es un placeholder para poder ver y probar el
formulario ya mismo. Se sustituirá cuando conectemos base de datos real
(valores existentes, taxonomía Morningstar completa) y la API de Twelve
Data (búsqueda de símbolos).
"""

import reflex as rx

from gestion_cartera.styles import SPACE_MD, SPACE_SM

TIPOS_OPERACION = ["Compra", "Venta", "Dividendo", "Script", "Prima"]

# MOCK: en el modelo real esto viene de la tabla BROKERS.
BROKERS_MOCK = ["ING", "Trade Republic", "Interactive Brokers"]

# MOCK: en el modelo real, esto sale de consultar la última OPERACION de
# este usuario en la cartera actualmente seleccionada (ORDER BY fecha DESC
# LIMIT 1). Aquí simulamos que esa última operación se hizo con ING.
ULTIMA_OPERACION_MOCK = {"broker": "ING"}

# MOCK: en el modelo real esto viene de la tabla VALORES (valores que el
# usuario ya tiene o que ya existen en el sistema).
VALORES_EXISTENTES_MOCK = [
    {"ticker": "ELE", "empresa": "Endesa"},
    {"ticker": "LDA", "empresa": "Línea Directa"},
    {"ticker": "SAN", "empresa": "Banco Santander"},
    {"ticker": "UNA", "empresa": "Unilever"},
]

# MOCK: esto simula lo que devolvería el endpoint /symbol_search de Twelve
# Data. Cuando lo conectemos de verdad, esta lista se sustituye por la
# respuesta real de la API (y ya no hace falta mantenerla a mano).
BUSQUEDA_SIMBOLOS_MOCK = [
    {"ticker": "MICC", "empresa": "Compañía de Helados Magnum", "bolsa": "NASDAQ"},
    {"ticker": "ITX.MC", "empresa": "Inditex", "bolsa": "Bolsa de Madrid"},
    {"ticker": "MC.PA", "empresa": "LVMH Moët Hennessy", "bolsa": "Euronext Paris"},
]

ZONAS = ["ESP", "EURO", "USA", "UK"]

# MOCK: muestra reducida de la taxonomía Morningstar (Supersector → Sector
# → Industria). La tabla SECTORES real deberá tener las ~69 industrias
# oficiales completas; esto es solo para poder probar el cascading select.
SECTORES_MOCK: dict[str, dict[str, list[str]]] = {
    "Cíclico": {
        "Consumo Cíclico": ["Automóviles", "Textil y Confección", "Distribución Minorista"],
        "Servicios Financieros": ["Banca", "Seguros"],
        "Inmobiliario": ["REIT Residencial", "REIT Comercial"],
    },
    "Defensivo": {
        "Consumo Defensivo": ["Alimentación", "Bebidas", "Higiene y Cuidado Personal"],
        "Sanidad": ["Farmacéuticas", "Equipamiento Médico"],
        "Servicios Públicos": ["Eléctricas", "Agua"],
    },
    "Sensible": {
        "Energía": ["Petróleo y Gas", "Energías Renovables"],
        "Industria": ["Manufactura", "Construcción"],
        "Tecnología": ["Software", "Semiconductores"],
        "Comunicación": ["Telecomunicaciones", "Medios"],
    },
}


class AltaOperacionState(rx.State):
    """Estado del formulario de alta de operación."""

    # --- Campos siempre presentes ---
    fecha: str = ""

    # --- Campo presente en todos los tipos (no mencionado como variable
    # en este ajuste, se mantiene sin cambios) ---
    broker: str = BROKERS_MOCK[0]

    # --- Tipo de operación: decide qué más se muestra ---
    tipo_operacion: str = "Compra"

    # --- Campos numéricos compartidos por varios tipos ---
    num_titulos: str = ""
    importe: str = ""
    retencion_destino: str = ""
    retencion_origen: str = ""
    observaciones: str = ""

    # --- Solo para "Script" ---
    tipo_derecho_script: str = "Compra"  # "Compra" | "Venta" (de derechos)

    # --- Selección del valor sobre el que se opera ---
    modo_valor: str = "existente"  # "existente" | "nuevo"
    valor_existente: str = ""  # ticker elegido de VALORES_EXISTENTES_MOCK

    # --- Sub-formulario "nuevo valor" (solo si modo_valor == "nuevo") ---
    busqueda_texto: str = ""
    ticker_nuevo: str = ""
    empresa_nueva: str = ""
    zona_nueva: str = ""
    supersector_nuevo: str = ""
    sector_nuevo: str = ""
    industria_nueva: str = ""

    def set_fecha(self, value: str):
        self.fecha = value

    def cargar_datos_iniciales(self):
        """Se ejecuta al cargar la página (on_load). Pone como bróker por
        defecto el usado en la última operación de este usuario con la
        cartera actualmente seleccionada; si no hay ninguna, se queda el
        primero de la lista.
        """
        self.broker = ULTIMA_OPERACION_MOCK.get("broker", BROKERS_MOCK[0])

    def set_broker(self, value: str):
        self.broker = value

    def set_tipo_operacion(self, value: str):
        self.tipo_operacion = value
        # Dar de alta un valor nuevo solo tiene sentido en una compra.
        if value != "Compra":
            self.modo_valor = "existente"

    def set_num_titulos(self, value: str):
        self.num_titulos = value

    def set_importe(self, value: str):
        self.importe = value

    def set_retencion_destino(self, value: str):
        self.retencion_destino = value

    def set_retencion_origen(self, value: str):
        self.retencion_origen = value

    def set_observaciones(self, value: str):
        self.observaciones = value

    def set_tipo_derecho_script(self, value: str | list[str]):
        self.tipo_derecho_script = value if isinstance(value, str) else (value[0] if value else "Compra")

    def set_modo_valor(self, value: str | list[str]):
        self.modo_valor = value if isinstance(value, str) else (value[0] if value else "")

    def set_valor_existente(self, value: str):
        self.valor_existente = value

    def set_busqueda_texto(self, value: str):
        self.busqueda_texto = value
        # Al cambiar el texto de búsqueda se descarta la selección previa.
        self.ticker_nuevo = ""
        self.empresa_nueva = ""

    def seleccionar_resultado_busqueda(self, ticker: str, empresa: str):
        self.ticker_nuevo = ticker
        self.empresa_nueva = empresa

    def set_zona_nueva(self, value: str):
        self.zona_nueva = value

    def set_supersector_nuevo(self, value: str):
        self.supersector_nuevo = value
        self.sector_nuevo = ""
        self.industria_nueva = ""

    def set_sector_nuevo(self, value: str):
        self.sector_nuevo = value
        self.industria_nueva = ""

    def set_industria_nueva(self, value: str):
        self.industria_nueva = value

    @rx.var
    def resultados_busqueda(self) -> list[dict[str, str]]:
        """Filtra BUSQUEDA_SIMBOLOS_MOCK por el texto escrito.

        Esto es exactamente lo que hará el endpoint /symbol_search de
        Twelve Data cuando lo conectemos: recibe texto, devuelve símbolos
        coincidentes.
        """
        if not self.busqueda_texto:
            return []
        texto = self.busqueda_texto.lower()
        return [
            r
            for r in BUSQUEDA_SIMBOLOS_MOCK
            if texto in r["ticker"].lower() or texto in r["empresa"].lower()
        ]

    @rx.var
    def sectores_disponibles(self) -> list[str]:
        if not self.supersector_nuevo:
            return []
        return list(SECTORES_MOCK.get(self.supersector_nuevo, {}).keys())

    @rx.var
    def industrias_disponibles(self) -> list[str]:
        if not self.supersector_nuevo or not self.sector_nuevo:
            return []
        return SECTORES_MOCK.get(self.supersector_nuevo, {}).get(self.sector_nuevo, [])

    @rx.var
    def importe_unitario(self) -> str:
        """Importe / NumTits. Calculado, no editable. SÍ se guarda."""
        try:
            num = float(self.num_titulos)
            imp = float(self.importe)
            if num == 0:
                return ""
            return f"{imp / num:.4f}"
        except ValueError:
            return ""

    @rx.var
    def importe_neto(self) -> str:
        """Importe - retenciones. Calculado, no editable, SOLO informativo
        (no se guarda en base de datos)."""
        try:
            imp = float(self.importe or 0)
            ret_o = float(self.retencion_origen or 0)
            ret_d = float(self.retencion_destino or 0)
            return f"{imp - ret_o - ret_d:.2f}"
        except ValueError:
            return ""

    def guardar_operacion(self):
        # Placeholder: aquí irá la validación y el guardado real en base
        # de datos (crear el VALOR nuevo si aplica, luego la OPERACION).
        # Campos a persistir según tipo (importe_neto NUNCA se guarda):
        #   Compra/Venta/Prima: fecha, broker, valor, num_titulos, importe,
        #       importe_unitario, observaciones
        #   Dividendo: + retencion_origen, retencion_destino
        #   Script: fecha, broker, valor, tipo_derecho_script, num_titulos,
        #       importe, retencion_origen, retencion_destino
        pass


def campo(label: str, *children) -> rx.Component:
    """Envoltorio simple: etiqueta + control, en columna."""
    return rx.flex(
        rx.text(label, size="2", weight="medium", color_scheme="gray"),
        *children,
        direction="column",
        spacing="1",
        width="100%",
    )


def campo_calculado(label: str, valor: rx.Var, nota: str | None = None) -> rx.Component:
    """Campo de solo lectura para valores calculados (importe unitario,
    importe neto...). Se muestra deshabilitado para dejar claro que no es
    editable."""
    children = [
        rx.text(label, size="2", weight="medium", color_scheme="gray"),
        rx.input(value=valor, disabled=True, width="100%"),
    ]
    if nota:
        children.append(rx.text(nota, size="1", color_scheme="gray"))
    return rx.flex(*children, direction="column", spacing="1", width="100%")


def resultado_busqueda_item(item: dict) -> rx.Component:
    return rx.button(
        rx.hstack(
            rx.text(item["ticker"], weight="bold"),
            rx.text(item["empresa"]),
            rx.spacer(),
            rx.text(item["bolsa"], size="1", color_scheme="gray"),
            width="100%",
        ),
        on_click=AltaOperacionState.seleccionar_resultado_busqueda(
            item["ticker"], item["empresa"]
        ),
        variant="soft",
        width="100%",
        justify="start",
    )


def subformulario_nuevo_valor() -> rx.Component:
    """Sub-formulario que solo aparece cuando el usuario elige dar de alta
    un valor nuevo (y la operación es una Compra)."""
    return rx.card(
        rx.flex(
            rx.heading("Dar de alta un valor nuevo", size="3"),
            campo(
                "Buscar valor (ticker o nombre)",
                rx.input(
                    placeholder="Ej: Inditex, ITX...",
                    value=AltaOperacionState.busqueda_texto,
                    on_change=AltaOperacionState.set_busqueda_texto,
                    width="100%",
                ),
            ),
            rx.cond(
                AltaOperacionState.busqueda_texto != "",
                rx.flex(
                    rx.foreach(
                        AltaOperacionState.resultados_busqueda,
                        resultado_busqueda_item,
                    ),
                    direction="column",
                    spacing="1",
                ),
            ),
            rx.cond(
                AltaOperacionState.ticker_nuevo != "",
                rx.flex(
                    rx.callout(
                        rx.text(
                            "Seleccionado: ",
                            AltaOperacionState.ticker_nuevo,
                            " — ",
                            AltaOperacionState.empresa_nueva,
                        ),
                        color_scheme="blue",
                        size="1",
                    ),
                    campo(
                        "Zona",
                        rx.select(
                            ZONAS,
                            placeholder="Elige zona",
                            value=AltaOperacionState.zona_nueva,
                            on_change=AltaOperacionState.set_zona_nueva,
                            width="100%",
                        ),
                    ),
                    rx.grid(
                        campo(
                            "Supersector",
                            rx.select(
                                list(SECTORES_MOCK.keys()),
                                placeholder="Elige supersector",
                                value=AltaOperacionState.supersector_nuevo,
                                on_change=AltaOperacionState.set_supersector_nuevo,
                                width="100%",
                            ),
                        ),
                        campo(
                            "Sector",
                            rx.select(
                                AltaOperacionState.sectores_disponibles,
                                placeholder="Elige sector",
                                value=AltaOperacionState.sector_nuevo,
                                on_change=AltaOperacionState.set_sector_nuevo,
                                disabled=AltaOperacionState.supersector_nuevo == "",
                                width="100%",
                            ),
                        ),
                        campo(
                            "Industria",
                            rx.select(
                                AltaOperacionState.industrias_disponibles,
                                placeholder="Elige industria",
                                value=AltaOperacionState.industria_nueva,
                                on_change=AltaOperacionState.set_industria_nueva,
                                disabled=AltaOperacionState.sector_nuevo == "",
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
        ),
        variant="surface",
        width="100%",
    )


def selector_de_valor() -> rx.Component:
    return rx.flex(
        rx.cond(
            AltaOperacionState.tipo_operacion == "Compra",
            rx.segmented_control.root(
                rx.segmented_control.item("Valor existente", value="existente"),
                rx.segmented_control.item("Dar de alta uno nuevo", value="nuevo"),
                value=AltaOperacionState.modo_valor,
                on_change=AltaOperacionState.set_modo_valor,
            ),
        ),
        rx.cond(
            AltaOperacionState.modo_valor == "existente",
            campo(
                "Valor",
                rx.select(
                    [f"{v['ticker']} — {v['empresa']}" for v in VALORES_EXISTENTES_MOCK],
                    placeholder="Elige un valor",
                    value=AltaOperacionState.valor_existente,
                    on_change=AltaOperacionState.set_valor_existente,
                    width="100%",
                ),
            ),
            subformulario_nuevo_valor(),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def campos_compra_venta_prima() -> rx.Component:
    """Compra, Venta y Prima comparten exactamente los mismos campos
    numéricos; solo Compra permite además dar de alta un valor nuevo
    (eso ya se resuelve en selector_de_valor)."""
    return rx.grid(
        campo(
            "Nº títulos",
            rx.input(
                type="number",
                value=AltaOperacionState.num_titulos,
                on_change=AltaOperacionState.set_num_titulos,
                width="100%",
            ),
        ),
        campo(
            "Importe",
            rx.input(
                type="number",
                value=AltaOperacionState.importe,
                on_change=AltaOperacionState.set_importe,
                width="100%",
            ),
        ),
        campo_calculado("Importe unitario", AltaOperacionState.importe_unitario),
        columns=rx.breakpoints(initial="1", md="3"),
        spacing="3",
        width="100%",
    )


def campos_dividendo() -> rx.Component:
    return rx.flex(
        rx.grid(
            campo(
                "Nº títulos",
                rx.input(
                    type="number",
                    value=AltaOperacionState.num_titulos,
                    on_change=AltaOperacionState.set_num_titulos,
                    width="100%",
                ),
            ),
            campo(
                "Importe",
                rx.input(
                    type="number",
                    value=AltaOperacionState.importe,
                    on_change=AltaOperacionState.set_importe,
                    width="100%",
                ),
            ),
            campo_calculado("Importe unitario", AltaOperacionState.importe_unitario),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="3",
            width="100%",
        ),
        rx.grid(
            campo(
                "Retención origen",
                rx.input(
                    type="number",
                    value=AltaOperacionState.retencion_origen,
                    on_change=AltaOperacionState.set_retencion_origen,
                    width="100%",
                ),
            ),
            campo(
                "Retención destino",
                rx.input(
                    type="number",
                    value=AltaOperacionState.retencion_destino,
                    on_change=AltaOperacionState.set_retencion_destino,
                    width="100%",
                ),
            ),
            campo_calculado(
                "Importe neto",
                AltaOperacionState.importe_neto,
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


def campos_script() -> rx.Component:
    return rx.flex(
        campo(
            "Tipo de derecho",
            rx.segmented_control.root(
                rx.segmented_control.item("Compra de derechos", value="Compra"),
                rx.segmented_control.item("Venta de derechos", value="Venta"),
                value=AltaOperacionState.tipo_derecho_script,
                on_change=AltaOperacionState.set_tipo_derecho_script,
            ),
        ),
        rx.grid(
            campo(
                "Nº títulos recibidos",
                rx.input(
                    type="number",
                    value=AltaOperacionState.num_titulos,
                    on_change=AltaOperacionState.set_num_titulos,
                    width="100%",
                ),
            ),
            campo(
                rx.cond(
                    AltaOperacionState.tipo_derecho_script == "Compra",
                    "Importe compra derechos",
                    "Importe venta derechos",
                ),
                rx.input(
                    type="number",
                    value=AltaOperacionState.importe,
                    on_change=AltaOperacionState.set_importe,
                    width="100%",
                ),
            ),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="3",
            width="100%",
        ),
        rx.cond(
            AltaOperacionState.tipo_derecho_script == "Venta",
            rx.grid(
                campo(
                    "Retención origen",
                    rx.input(
                        type="number",
                        value=AltaOperacionState.retencion_origen,
                        on_change=AltaOperacionState.set_retencion_origen,
                        width="100%",
                    ),
                ),
                campo(
                    "Retención destino",
                    rx.input(
                        type="number",
                        value=AltaOperacionState.retencion_destino,
                        on_change=AltaOperacionState.set_retencion_destino,
                        width="100%",
                    ),
                ),
                campo_calculado(
                    "Importe neto",
                    AltaOperacionState.importe_neto,
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


def campos_segun_tipo() -> rx.Component:
    return rx.match(
        AltaOperacionState.tipo_operacion,
        (("Compra", "Venta", "Prima"), campos_compra_venta_prima()),
        ("Dividendo", campos_dividendo()),
        ("Script", campos_script()),
        campos_compra_venta_prima(),  # fallback por defecto
    )


def alta_operacion_form() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading("Nueva operación", size="4"),
            rx.grid(
                campo(
                    "Tipo de operación",
                    rx.select(
                        TIPOS_OPERACION,
                        value=AltaOperacionState.tipo_operacion,
                        on_change=AltaOperacionState.set_tipo_operacion,
                        width="100%",
                    ),
                ),
                campo(
                    "Fecha",
                    rx.input(
                        type="date",
                        value=AltaOperacionState.fecha,
                        on_change=AltaOperacionState.set_fecha,
                        width="100%",
                    ),
                ),
                campo(
                    "Bróker",
                    rx.select(
                        BROKERS_MOCK,
                        value=AltaOperacionState.broker,
                        on_change=AltaOperacionState.set_broker,
                        width="100%",
                    ),
                ),
                columns=rx.breakpoints(initial="1", md="3"),
                spacing="3",
                width="100%",
            ),
            selector_de_valor(),
            campos_segun_tipo(),
            campo(
                "Observaciones",
                rx.text_area(
                    placeholder="Observaciones (opcional)",
                    value=AltaOperacionState.observaciones,
                    on_change=AltaOperacionState.set_observaciones,
                    width="100%",
                ),
            ),
            rx.hstack(
                rx.button(
                    "Guardar operación",
                    on_click=AltaOperacionState.guardar_operacion,
                ),
                rx.button("Cancelar", variant="soft", color_scheme="gray"),
                spacing="3",
                padding_top=SPACE_SM,
            ),
            direction="column",
            spacing="5",
        ),
        width="100%",
        max_width="720px",
        padding=SPACE_MD,
    )
"""Formulario de alta de operación, conectado a base de datos real y a
la búsqueda de símbolos de Twelve Data.

Los campos visibles cambian según el tipo de operación:
- Compra / Venta / Prima: NumTits, Importe, Importe unitario (calculado),
  Observaciones. Solo "Compra" permite dar de alta un valor nuevo.
- Dividendo: + Retención origen/destino, Importe neto (informativo, no
  se guarda).
- Script: Tipo de derecho (compra/venta), Nº títulos recibidos, Importe
  (según tipo de derecho). Con "Venta de derechos" además Retenciones e
  Importe neto (informativo); con "Compra de derechos" no aplican.
- Observaciones: siempre visible, para los 5 tipos.
"""

from datetime import date

import reflex as rx

from gestion_cartera.format_utils import formatear_numero
from gestion_cartera.services import twelvedata
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.styles import SPACE_MD, SPACE_SM
from gestion_cartera.operaciones_db import (
    TickerDuplicadoError,
    buscar_operacion_compensatoria,
    calcular_saldo,
    crear_operacion,
    crear_valor,
    obtener_broker_id_por_nombre,
    obtener_brokers,
    obtener_cartera_id,
    obtener_sector_id,
    obtener_sectores,
    obtener_ultimo_broker,
    obtener_valor_id_por_ticker_mercado,
    obtener_valores,
    obtener_valores_por_ticker,
    validar_saldo_nunca_negativo,
)

# Tipos de operación que no alteran el nº de títulos en cartera y por
# tanto no participan en el cálculo del SALDO (ver calcular_saldo).
TIPOS_QUE_VALIDAN_SALDO = ("Venta", "Dividendo", "Prima")

TIPOS_OPERACION = ["Compra", "Venta", "Dividendo", "Script", "Prima"]
ZONAS = ["ESP", "EURO", "USA", "UK"]
# Fijos: son los 3 Super Sectores de Morningstar, no cambian.
SUPERSECTORES = ["Cíclico", "Defensivo", "Sensible"]


class AltaOperacionState(rx.State):
    """Estado del formulario de alta de operación."""

    # --- Datos cargados de la base de datos al abrir la página ---
    brokers_disponibles: list[str] = []
    valores_disponibles_raw: list[dict] = []
    sectores_todos: list[dict] = []
    id_cartera: int = 0

    # --- Campos siempre presentes ---
    fecha: str = ""
    broker: str = ""
    tipo_operacion: str = "Compra"
    num_titulos: str = ""
    importe: str = ""
    retencion_destino: str = ""
    retencion_origen: str = ""
    observaciones: str = ""

    # --- Solo para "Script" ---
    tipo_derecho_script: str = "Compra"  # "Compra" | "Venta" (de derechos)

    # --- Selección del valor sobre el que se opera ---
    modo_valor: str = "existente"  # "existente" | "nuevo"
    valor_existente: str = ""  # "TICKER — Empresa"

    # --- Sub-formulario "nuevo valor" ---
    busqueda_texto: str = ""
    busqueda_error: str = ""
    resultados_busqueda: list[dict] = []
    ticker_nuevo: str = ""
    empresa_nueva: str = ""
    moneda_nueva: str = ""
    mercado_nuevo: str = ""
    zona_nueva: str = ""
    supersector_nuevo: str = ""
    sector_nuevo: str = ""
    industria_nueva: str = ""

    # Si el ticker elegido ya existe en el catálogo (en cualquier
    # mercado), aquí se explica por qué. `requiere_confirmacion_mercado`
    # distingue el caso "existe pero en OTRO mercado" (se puede continuar,
    # confirmando) del caso "existe exactamente igual" (bloqueo, ver
    # crear_valor/TickerDuplicadoError al guardar).
    advertencia_ticker: str = ""
    requiere_confirmacion_mercado: bool = False
    confirmar_mercado_distinto: bool = False

    # --- Resultado de guardar ---
    guardado_ok: bool = False
    guardado_mensaje: str = ""
    guardado_error: str = ""

    async def cargar_datos_iniciales(self):
        """on_load de la página: carga catálogos y precarga el bróker
        por defecto (el de la última operación de este usuario en la
        cartera actualmente seleccionada en el dashboard)."""
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return

        # Import perezoso para no arrastrar el árbol de páginas al arrancar.
        from gestion_cartera.states.portfolio_state import PortfolioState

        portfolio_state = await self.get_state(PortfolioState)

        self.brokers_disponibles = obtener_brokers()
        self.valores_disponibles_raw = obtener_valores()
        self.sectores_todos = obtener_sectores()

        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )
        self.id_cartera = id_cartera or 0
        ultimo_broker = obtener_ultimo_broker(id_cartera) if id_cartera else None
        if ultimo_broker:
            self.broker = ultimo_broker
        elif self.brokers_disponibles:
            self.broker = self.brokers_disponibles[0]

    def set_fecha(self, value: str):
        self.fecha = value

    def set_broker(self, value: str):
        self.broker = value

    def set_tipo_operacion(self, value: str):
        self.tipo_operacion = value
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
        self.tipo_derecho_script = (
            value if isinstance(value, str) else (value[0] if value else "Compra")
        )

    def set_modo_valor(self, value: str | list[str]):
        self.modo_valor = value if isinstance(value, str) else (value[0] if value else "")

    def set_valor_existente(self, value: str):
        self.valor_existente = value

    def set_busqueda_texto(self, value: str):
        """Actualiza el texto inmediatamente (para que el input responda
        sin esperar), y descarta la selección anterior."""
        self.busqueda_texto = value
        self.ticker_nuevo = ""
        self.empresa_nueva = ""
        self.moneda_nueva = ""
        self.mercado_nuevo = ""
        self.busqueda_error = ""
        self.advertencia_ticker = ""
        self.requiere_confirmacion_mercado = False
        self.confirmar_mercado_distinto = False

    def buscar_valor(self, value: str):
        """Este handler va con .debounce() en el componente: solo se
        ejecuta 400ms después de que el usuario deje de teclear."""
        if not value:
            self.resultados_busqueda = []
            return
        try:
            self.resultados_busqueda = twelvedata.buscar_simbolo(value)
        except Exception as e:
            self.resultados_busqueda = []
            self.busqueda_error = f"No se pudo buscar: {e}"

    def seleccionar_resultado_busqueda(self, ticker: str, empresa: str, moneda: str, mercado: str):
        self.ticker_nuevo = ticker
        self.empresa_nueva = empresa
        self.moneda_nueva = moneda
        self.mercado_nuevo = mercado
        self.confirmar_mercado_distinto = False

        existentes = obtener_valores_por_ticker(ticker)
        if not existentes:
            self.advertencia_ticker = ""
            self.requiere_confirmacion_mercado = False
        elif any(v["mercado"] == mercado for v in existentes):
            self.advertencia_ticker = (
                f"Ya tienes «{ticker}» registrado exactamente en este mercado "
                f"({mercado}). Selecciónalo como valor existente en vez de darlo de "
                "alta de nuevo."
            )
            self.requiere_confirmacion_mercado = False
        else:
            mercados = ", ".join(sorted({v["mercado"] for v in existentes}))
            self.advertencia_ticker = (
                f"Ya tienes un valor con el ticker «{ticker}» en tu catálogo, pero en "
                f"otro mercado ({mercados}). Si es la misma empresa cotizando en un "
                "mercado distinto (p.ej. una acción y su ADR), confirma abajo para "
                "continuar; si ha sido un error, elige «Valor existente» en su lugar."
            )
            self.requiere_confirmacion_mercado = True

    def set_confirmar_mercado_distinto(self, value: bool):
        self.confirmar_mercado_distinto = value

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
    def valores_disponibles(self) -> list[str]:
        return [
            f"{v['ticker']} ({v['mercado']}) — {v['empresa']}" for v in self.valores_disponibles_raw
        ]

    @rx.var
    def sectores_disponibles(self) -> list[str]:
        if not self.supersector_nuevo:
            return []
        vistos = []
        for s in self.sectores_todos:
            if s["supersector"] == self.supersector_nuevo and s["sector"] not in vistos:
                vistos.append(s["sector"])
        return vistos

    @rx.var
    def industrias_disponibles(self) -> list[str]:
        if not self.supersector_nuevo or not self.sector_nuevo:
            return []
        return [
            s["grupo"]
            for s in self.sectores_todos
            if s["supersector"] == self.supersector_nuevo and s["sector"] == self.sector_nuevo
        ]

    @rx.var
    def id_valor_para_validacion(self) -> int:
        """Id del Valor seleccionado en 'Valor existente', o 0 si no se
        puede resolver todavía (nada elegido, o modo 'nuevo')."""
        if self.modo_valor != "existente" or not self.valor_existente:
            return 0
        ticker_mercado, _, _ = self.valor_existente.partition(" — ")
        ticker, _, resto = ticker_mercado.partition(" (")
        mercado = resto.rstrip(")")
        return obtener_valor_id_por_ticker_mercado(ticker, mercado) or 0

    def _calcular_validacion_saldo(self) -> tuple[str, bool]:
        """Combina dos comprobaciones sobre la operación en curso de alta:

        1. `_validar_punto_saldo`: para Venta/Dividendo/Prima, el número
           de títulos contra el saldo EN LA FECHA de esta operación
           (mensajes concretos, con sugerencia de compensación para
           Dividendo).
        2. `_validar_timeline_alta`: para Compra/Venta/Script, que dar de
           alta esta operación no deje el saldo en negativo en NINGÚN
           punto de la línea temporal -- p. ej. una Venta con fecha
           retroactiva anterior a otra Venta ya existente, que (1) no
           detecta porque solo mira el saldo hasta la fecha de esta
           operación, no lo que pasa después.

        Se devuelve el primer mensaje no vacío que aparezca."""
        if self.tipo_operacion in TIPOS_QUE_VALIDAN_SALDO:
            mensaje, bloqueo = self._validar_punto_saldo()
            if mensaje:
                return mensaje, bloqueo

        if self.tipo_operacion in ("Compra", "Venta", "Script"):
            mensaje, bloqueo = self._validar_timeline_alta()
            if mensaje:
                return mensaje, bloqueo

        return "", False

    def _validar_punto_saldo(self) -> tuple[str, bool]:
        """(mensaje, bloqueo). mensaje == "" si no hay nada que avisar."""
        if (
            not self.num_titulos
            or not self.valor_existente
            or not self.broker
            or not self.fecha
            or not self.id_cartera
        ):
            return "", False
        try:
            num = float(self.num_titulos)
            fecha = date.fromisoformat(self.fecha)
        except ValueError:
            return "", False
        id_valor = self.id_valor_para_validacion
        id_broker = obtener_broker_id_por_nombre(self.broker)
        if not id_valor or id_broker is None:
            return "", False
        saldo = calcular_saldo(self.id_cartera, id_valor, id_broker, fecha)

        if self.tipo_operacion == "Venta":
            if num > saldo:
                return (
                    f"No puedes vender {num:g} títulos: el saldo disponible en este bróker "
                    f"a esta fecha es {saldo:g}.",
                    True,
                )
            return "", False

        if self.tipo_operacion == "Prima":
            if num > saldo:
                return (
                    f"No puedes cobrar una prima por {num:g} títulos: el saldo disponible en "
                    f"este bróker a esta fecha es {saldo:g}.",
                    True,
                )
            if num < saldo:
                return (
                    f"Cobras la prima por menos títulos ({num:g}) de los que tienes en saldo "
                    f"({saldo:g}).",
                    False,
                )
            return "", False

        # Dividendo
        if num == saldo:
            return "", False
        diferencia = abs(num - saldo)
        compensacion = buscar_operacion_compensatoria(
            self.id_cartera, id_valor, id_broker, diferencia, fecha
        )
        if compensacion:
            return (
                f"El nº de títulos ({num:g}) no coincide con el saldo ({saldo:g}), pero la "
                f"diferencia coincide con una {compensacion['tipo_operacion']} de "
                f"{compensacion['num_titulos']:g} títulos el {compensacion['fecha_mostrar']}.",
                False,
            )
        return (
            f"El nº de títulos ({num:g}) no coincide con el saldo ({saldo:g}) y no hay "
            "ninguna Compra/Venta reciente (últimos 30 días) que lo explique. Anula la "
            "operación y revisa el número de títulos.",
            True,
        )

    def _validar_timeline_alta(self) -> tuple[str, bool]:
        """Para Compra/Venta/Script: comprueba que añadir esta operación
        no deje el saldo en negativo en NINGÚN punto de la línea
        temporal (no solo en su propia fecha). Sin esto, una Venta con
        fecha retroactiva anterior a otra Venta ya existente pasaría el
        chequeo de `_validar_punto_saldo` (que solo mira el saldo hasta
        SU fecha) y dejaría a esa Venta posterior sin saldo suficiente."""
        if (
            not self.num_titulos
            or not self.valor_existente
            or not self.broker
            or not self.fecha
            or not self.id_cartera
        ):
            return "", False
        try:
            num = float(self.num_titulos)
            fecha = date.fromisoformat(self.fecha)
        except ValueError:
            return "", False
        id_valor = self.id_valor_para_validacion
        id_broker = obtener_broker_id_por_nombre(self.broker)
        if not id_valor or id_broker is None:
            return "", False

        error = validar_saldo_nunca_negativo(
            self.id_cartera,
            id_valor,
            id_broker,
            operacion_simulada={
                "fecha": fecha,
                "tipo_operacion": self.tipo_operacion,
                "num_titulos": num,
            },
        )
        if error:
            return error, True
        return "", False

    @rx.var
    def aviso_saldo(self) -> str:
        mensaje, _ = self._calcular_validacion_saldo()
        return mensaje

    @rx.var
    def bloqueo_saldo(self) -> bool:
        _, bloqueo = self._calcular_validacion_saldo()
        return bloqueo

    @rx.var
    def importe_unitario(self) -> str:
        try:
            num = float(self.num_titulos)
            imp = float(self.importe)
            if num == 0:
                return ""
            return formatear_numero(imp / num)
        except ValueError:
            return ""

    @rx.var
    def importe_neto(self) -> str:
        try:
            imp = float(self.importe or 0)
            ret_o = float(self.retencion_origen or 0)
            ret_d = float(self.retencion_destino or 0)
            return formatear_numero(imp - ret_o - ret_d)
        except ValueError:
            return ""

    def _reset_formulario(self):
        self.num_titulos = ""
        self.importe = ""
        self.retencion_origen = ""
        self.retencion_destino = ""
        self.observaciones = ""
        self.valor_existente = ""
        self.busqueda_texto = ""
        self.resultados_busqueda = []
        self.ticker_nuevo = ""
        self.empresa_nueva = ""
        self.moneda_nueva = ""
        self.mercado_nuevo = ""
        self.zona_nueva = ""
        self.supersector_nuevo = ""
        self.sector_nuevo = ""
        self.industria_nueva = ""
        self.modo_valor = "existente"
        self.advertencia_ticker = ""
        self.requiere_confirmacion_mercado = False
        self.confirmar_mercado_distinto = False

    def cancelar_formulario(self):
        """Vacía el formulario y los mensajes de guardado/error. Es el
        handler público que usan los botones "Cancelar" y "Cerrar" (el
        método `_reset_formulario` lleva guión bajo y por eso no se puede
        enganchar directamente a un on_click)."""
        self._reset_formulario()
        self.guardado_ok = False
        self.guardado_mensaje = ""
        self.guardado_error = ""

    async def guardar_operacion(self):
        self.guardado_error = ""
        self.guardado_ok = False

        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            self.guardado_error = "Debes iniciar sesión."
            return

        from gestion_cartera.states.portfolio_state import PortfolioState

        portfolio_state = await self.get_state(PortfolioState)
        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )
        if id_cartera is None:
            self.guardado_error = "No se ha encontrado la cartera seleccionada."
            return

        if not self.fecha:
            self.guardado_error = "Indica la fecha de la operación."
            return

        mensaje, bloqueo = self._calcular_validacion_saldo()
        if bloqueo:
            self.guardado_error = mensaje
            return

        # --- Resolver el valor ---
        if self.tipo_operacion == "Compra" and self.modo_valor == "nuevo":
            if not self.ticker_nuevo or not self.zona_nueva or not self.industria_nueva:
                self.guardado_error = (
                    "Completa la búsqueda del valor, la zona y la clasificación sectorial."
                )
                return
            id_sector = obtener_sector_id(
                self.supersector_nuevo, self.sector_nuevo, self.industria_nueva
            )
            if id_sector is None:
                self.guardado_error = "No se ha encontrado esa combinación de sector."
                return
            if self.requiere_confirmacion_mercado and not self.confirmar_mercado_distinto:
                self.guardado_error = (
                    "Confirma que es un valor distinto (mercado diferente) antes de guardar."
                )
                return
            try:
                id_valor = crear_valor(
                    self.ticker_nuevo,
                    self.empresa_nueva,
                    id_sector,
                    self.mercado_nuevo,
                    self.zona_nueva,
                    self.moneda_nueva,
                )
            except TickerDuplicadoError as e:
                self.guardado_error = str(e)
                return
            self.valores_disponibles_raw = obtener_valores()
        else:
            if not self.valor_existente:
                self.guardado_error = "Selecciona un valor."
                return
            ticker_mercado, _, _ = self.valor_existente.partition(" — ")
            ticker, _, resto = ticker_mercado.partition(" (")
            mercado = resto.rstrip(")")
            id_valor = obtener_valor_id_por_ticker_mercado(ticker, mercado)
            if id_valor is None:
                self.guardado_error = "No se ha encontrado el valor seleccionado."
                return

        id_broker = obtener_broker_id_por_nombre(self.broker)
        if id_broker is None:
            self.guardado_error = "Bróker no válido."
            return

        try:
            num_titulos = float(self.num_titulos)
            importe = float(self.importe)
        except ValueError:
            self.guardado_error = "Revisa los importes numéricos."
            return

        importe_unitario = None
        if self.tipo_operacion != "Script" and num_titulos:
            importe_unitario = importe / num_titulos

        retencion_origen = None
        retencion_destino = None
        tipo_derecho_script = None
        if self.tipo_operacion == "Dividendo":
            retencion_origen = float(self.retencion_origen or 0)
            retencion_destino = float(self.retencion_destino or 0)
        elif self.tipo_operacion == "Script":
            tipo_derecho_script = self.tipo_derecho_script
            if self.tipo_derecho_script == "Venta":
                retencion_origen = float(self.retencion_origen or 0)
                retencion_destino = float(self.retencion_destino or 0)

        crear_operacion(
            id_cartera=id_cartera,
            id_valor=id_valor,
            id_broker=id_broker,
            tipo_operacion=self.tipo_operacion,
            fecha=date.fromisoformat(self.fecha),
            num_titulos=num_titulos,
            importe=importe,
            importe_unitario=importe_unitario,
            retencion_origen=retencion_origen,
            retencion_destino=retencion_destino,
            tipo_derecho_script=tipo_derecho_script,
            observaciones=self.observaciones or None,
        )

        self.guardado_ok = True
        self.guardado_mensaje = "Operación guardada correctamente."
        self._reset_formulario()

        # Si la página OPERACIONES está abierta (este formulario se usa
        # dentro de su diálogo "Alta Operación"), refrescamos su listado
        # para que la nueva operación aparezca sin recargar la página.
        from gestion_cartera.states.operaciones_state import OperacionesState

        operaciones_state = await self.get_state(OperacionesState)
        await operaciones_state.cargar_datos()


def campo(label: str, *children) -> rx.Component:
    return rx.flex(
        rx.text(label, size="2", weight="medium", color_scheme="gray"),
        *children,
        direction="column",
        spacing="1",
        width="100%",
    )


def campo_calculado(label: str, valor: rx.Var, nota: str | None = None) -> rx.Component:
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
            item["ticker"], item["empresa"], item["moneda"], item["bolsa"]
        ),
        variant="soft",
        width="100%",
        justify="start",
    )


def subformulario_nuevo_valor() -> rx.Component:
    return rx.card(
        rx.flex(
            rx.heading("Dar de alta un valor nuevo", size="3"),
            campo(
                "Buscar valor (ticker o nombre)",
                rx.input(
                    placeholder="Ej: Inditex, ITX...",
                    value=AltaOperacionState.busqueda_texto,
                    on_change=[
                        AltaOperacionState.set_busqueda_texto,
                        AltaOperacionState.buscar_valor.debounce(400),
                    ],
                    width="100%",
                ),
            ),
            rx.cond(
                AltaOperacionState.busqueda_error != "",
                rx.callout(AltaOperacionState.busqueda_error, color_scheme="red", size="1"),
            ),
            rx.cond(
                AltaOperacionState.busqueda_texto != "",
                rx.flex(
                    rx.foreach(AltaOperacionState.resultados_busqueda, resultado_busqueda_item),
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
                            " (",
                            AltaOperacionState.moneda_nueva,
                            ") · ",
                            AltaOperacionState.mercado_nuevo,
                        ),
                        color_scheme="blue",
                        size="1",
                    ),
                    rx.cond(
                        AltaOperacionState.advertencia_ticker != "",
                        rx.flex(
                            rx.callout(
                                AltaOperacionState.advertencia_ticker,
                                color_scheme=rx.cond(
                                    AltaOperacionState.requiere_confirmacion_mercado,
                                    "amber",
                                    "red",
                                ),
                                size="1",
                            ),
                            rx.cond(
                                AltaOperacionState.requiere_confirmacion_mercado,
                                rx.text(
                                    rx.checkbox(
                                        checked=AltaOperacionState.confirmar_mercado_distinto,
                                        on_change=AltaOperacionState.set_confirmar_mercado_distinto,
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
                                SUPERSECTORES,
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
                                key=AltaOperacionState.supersector_nuevo,
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
                                key=AltaOperacionState.supersector_nuevo + "|" + AltaOperacionState.sector_nuevo,
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
                rx.cond(
                    AltaOperacionState.valores_disponibles.length() > 0,
                    rx.select(
                        AltaOperacionState.valores_disponibles,
                        placeholder="Elige un valor",
                        value=AltaOperacionState.valor_existente,
                        on_change=AltaOperacionState.set_valor_existente,
                        width="100%",
                    ),
                    rx.text(
                        "Todavía no hay valores en cartera. Registra una Compra primero.",
                        size="2",
                        color_scheme="gray",
                    ),
                ),
            ),
            subformulario_nuevo_valor(),
        ),
        direction="column",
        spacing="3",
        width="100%",
    )


def campos_compra_venta_prima() -> rx.Component:
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
            "Importe (€)",
            rx.input(
                type="number",
                value=AltaOperacionState.importe,
                on_change=AltaOperacionState.set_importe,
                width="100%",
            ),
        ),
        campo_calculado("Importe unitario (€)", AltaOperacionState.importe_unitario),
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
                "Importe (€)",
                rx.input(
                    type="number",
                    value=AltaOperacionState.importe,
                    on_change=AltaOperacionState.set_importe,
                    width="100%",
                ),
            ),
            campo_calculado("Importe unitario (€)", AltaOperacionState.importe_unitario),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="3",
            width="100%",
        ),
        rx.grid(
            campo(
                "Retención origen (€)",
                rx.input(
                    type="number",
                    value=AltaOperacionState.retencion_origen,
                    on_change=AltaOperacionState.set_retencion_origen,
                    width="100%",
                ),
            ),
            campo(
                "Retención destino (€)",
                rx.input(
                    type="number",
                    value=AltaOperacionState.retencion_destino,
                    on_change=AltaOperacionState.set_retencion_destino,
                    width="100%",
                ),
            ),
            campo_calculado(
                "Importe neto (€)",
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
                    "Importe compra derechos (€)",
                    "Importe venta derechos (€)",
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
                    "Retención origen (€)",
                    rx.input(
                        type="number",
                        value=AltaOperacionState.retencion_origen,
                        on_change=AltaOperacionState.set_retencion_origen,
                        width="100%",
                    ),
                ),
                campo(
                    "Retención destino (€)",
                    rx.input(
                        type="number",
                        value=AltaOperacionState.retencion_destino,
                        on_change=AltaOperacionState.set_retencion_destino,
                        width="100%",
                    ),
                ),
                campo_calculado(
                    "Importe neto (€)",
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
        campos_compra_venta_prima(),
    )


def alta_operacion_form(on_cancel: rx.EventHandler | None = None) -> rx.Component:
    """`on_cancel` es opcional: cuando este formulario se usa dentro de un
    diálogo (página OPERACIONES), se le pasa el evento que lo cierra, y se
    conecta tanto al botón "Cancelar" como al "Cerrar" que aparece tras
    guardar con éxito. Si no se pasa nada (uso independiente), esos
    botones simplemente no hacen nada más que lo que ya hacían."""
    botones_cierre = [AltaOperacionState.cancelar_formulario] + (
        [on_cancel] if on_cancel is not None else []
    )
    return rx.card(
        rx.flex(
            rx.heading("Nueva operación", size="4"),
            rx.text(
                "Todos los importes se registran en euros (€).",
                size="1",
                color_scheme="gray",
            ),
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
                    rx.cond(
                        AltaOperacionState.brokers_disponibles.length() > 0,
                        rx.select(
                            AltaOperacionState.brokers_disponibles,
                            value=AltaOperacionState.broker,
                            on_change=AltaOperacionState.set_broker,
                            width="100%",
                        ),
                        rx.text("Cargando brókers…", size="2", color_scheme="gray"),
                    ),
                ),
                columns=rx.breakpoints(initial="1", md="3"),
                spacing="3",
                width="100%",
            ),
            selector_de_valor(),
            campos_segun_tipo(),
            rx.cond(
                AltaOperacionState.aviso_saldo != "",
                rx.callout(
                    AltaOperacionState.aviso_saldo,
                    color_scheme=rx.cond(AltaOperacionState.bloqueo_saldo, "red", "amber"),
                    size="1",
                ),
            ),
            campo(
                "Observaciones",
                rx.text_area(
                    placeholder="Observaciones (opcional)",
                    value=AltaOperacionState.observaciones,
                    on_change=AltaOperacionState.set_observaciones,
                    width="100%",
                ),
            ),
            rx.cond(
                AltaOperacionState.guardado_error != "",
                rx.callout(AltaOperacionState.guardado_error, color_scheme="red", size="1"),
            ),
            rx.cond(
                AltaOperacionState.guardado_ok,
                rx.hstack(
                    rx.callout(
                        AltaOperacionState.guardado_mensaje, color_scheme="green", size="1"
                    ),
                    *(
                        [
                            rx.button(
                                "Cerrar", variant="soft", on_click=botones_cierre, type="button"
                            )
                        ]
                        if on_cancel is not None
                        else []
                    ),
                    align="center",
                    spacing="3",
                ),
            ),
            rx.hstack(
                rx.button("Guardar operación", on_click=AltaOperacionState.guardar_operacion),
                rx.button(
                    "Cancelar",
                    variant="soft",
                    color_scheme="gray",
                    type="button",
                    on_click=botones_cierre,
                ),
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
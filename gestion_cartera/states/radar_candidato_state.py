"""Estado de la lista de posibles compras de RADAR (punto 4 del
encargo): alta de un valor en seguimiento (reutilizando el mismo
buscador/alta de valor nuevo que el formulario de Operaciones, ver
components/alta_operacion_form.py), listado con color de aviso, edición
y borrado, y refresco de cotizaciones (Yahoo Finance, mismo patrón que
states/cartera_state.py).

`_RadarCandidatoMixin` tiene toda la lógica (vars, formulario,
edición, refresco de cotizaciones...) y NO es un estado en sí mismo
(`mixin=True`): es una plantilla de la que salen dos estados
CONCRETOS e independientes, `RadarCandidatoState` (Largo Plazo) y
`RadarCandidatoCortoPlazoState` (Corto Plazo, punto 7 del encargo),
cada uno con su propio `TIPO_LISTA` y su propio almacenamiento.

OJO: la primera versión de este fichero hacía
`class RadarCandidatoCortoPlazoState(RadarCandidatoState)` (herencia
directa entre dos estados concretos) pensando que cada subclase de un
`rx.State` tendría su propio almacenamiento -- en Reflex NO es así:
los vars declarados en la clase padre viven en el almacenamiento del
padre, así que las dos listas compartían literalmente los mismos
datos (alta/edición/borrado en una aparecía en la otra). La forma
correcta de reutilizar lógica entre dos estados hermanos e
independientes es un mixin (`rx.State, mixin=True`), que no participa
del árbol de sub-estados: cada clase que lo combina con `rx.State`
recibe su propia copia de los vars.
"""

import asyncio
from typing import ClassVar

import reflex as rx

from gestion_cartera.cartera_db import guardar_cotizacion
from gestion_cartera.operaciones_db import (
    TickerDuplicadoError,
    crear_valor,
    obtener_sector_id,
    obtener_sectores,
    obtener_valor_id_por_ticker_mercado,
    obtener_valores,
    obtener_valores_por_ticker,
)
from gestion_cartera.radar_db import (
    CandidatoDuplicadoError,
    actualizar_candidato,
    crear_candidato,
    eliminar_candidato,
    obtener_candidatos,
    obtener_valores_en_lista,
)
from gestion_cartera.services import twelvedata, yahoo_finance
from gestion_cartera.states.auth_state import AuthState

# Igual que states/cartera_state.PAUSA_ENTRE_COTIZACIONES: margen de
# prudencia entre peticiones a Yahoo Finance, no un límite documentado.
PAUSA_ENTRE_COTIZACIONES = 1


class _RadarCandidatoMixin(rx.State, mixin=True):
    # ClassVar (no es un state var de Reflex): cada estado concreto que
    # use este mixin (ver RadarCandidatoState/RadarCandidatoCortoPlazoState,
    # al final del fichero) lo sobrescribe con su propio valor.
    TIPO_LISTA: ClassVar[str] = "Largo Plazo"
    # Solo la lista de Largo Plazo entra en el cálculo del gráfico
    # "Objetivo vs. real aplicando compras" (punto 6) -- Corto Plazo no
    # debe tocar ese balance (punto 7 del encargo).
    ACTUALIZA_PROYECCION: ClassVar[bool] = True

    candidatos: list[dict] = []
    actualizando_cotizaciones: bool = False
    cotizaciones_error: str = ""

    # --- Formulario de alta ------------------------------------------------
    mostrar_formulario: bool = False
    valores_disponibles_raw: list[dict] = []
    sectores_todos: list[dict] = []

    modo_valor: str = "existente"  # "existente" | "nuevo"
    valor_existente: str = ""  # "TICKER (MERCADO) — Empresa"
    busqueda_valor_existente: str = ""

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
    advertencia_ticker: str = ""
    requiere_confirmacion_mercado: bool = False
    confirmar_mercado_distinto: bool = False

    importe_invertir: str = ""
    precio_max: str = ""
    precio_min: str = ""
    guardado_error: str = ""

    # --- Edición inline de una fila -----------------------------------------
    editando_id: int = 0
    editando_importe: str = ""
    editando_precio_max: str = ""
    editando_precio_min: str = ""
    editando_error: str = ""

    async def cargar_datos(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return
        id_usuario = auth_state.current_user["id"]
        self.candidatos = obtener_candidatos(id_usuario, self.TIPO_LISTA)
        self.valores_disponibles_raw = obtener_valores()
        self.sectores_todos = obtener_sectores()
        return type(self).refrescar_cotizaciones

    @rx.event(background=True)
    async def refrescar_cotizaciones(self):
        async with self:
            if self.actualizando_cotizaciones:
                return
            self.actualizando_cotizaciones = True
            self.cotizaciones_error = ""
            auth_state = await self.get_state(AuthState)
            id_usuario = auth_state.current_user["id"] if auth_state.current_user else None
            tipo_lista = self.TIPO_LISTA

        valores = obtener_valores_en_lista(id_usuario, tipo_lista) if id_usuario else []

        errores = []
        for i, v in enumerate(valores):
            try:
                cot = yahoo_finance.obtener_cotizacion(v["ticker"], v["moneda"], v["mercado"])
                guardar_cotizacion(
                    v["id_valor"], cot["cotizacion_divisa"], cot["cotizacion_eur"], cot["actualizada_en"]
                )
            except Exception as e:
                errores.append(f"{v['mercado']}:{v['ticker']}: {e}")
            if i < len(valores) - 1:
                await asyncio.sleep(PAUSA_ENTRE_COTIZACIONES)

        async with self:
            if id_usuario:
                self.candidatos = obtener_candidatos(id_usuario, tipo_lista)
            self.actualizando_cotizaciones = False
            if errores:
                self.cotizaciones_error = (
                    f"No se pudo actualizar la cotización de {len(errores)} valor(es): "
                    + "; ".join(errores[:5])
                    + ("…" if len(errores) > 5 else "")
                )

    def abrir_formulario(self):
        self.mostrar_formulario = True

    def _reset_formulario(self):
        self.modo_valor = "existente"
        self.valor_existente = ""
        self.busqueda_valor_existente = ""
        self.busqueda_texto = ""
        self.busqueda_error = ""
        self.resultados_busqueda = []
        self.ticker_nuevo = ""
        self.empresa_nueva = ""
        self.moneda_nueva = ""
        self.mercado_nuevo = ""
        self.zona_nueva = ""
        self.supersector_nuevo = ""
        self.sector_nuevo = ""
        self.industria_nueva = ""
        self.advertencia_ticker = ""
        self.requiere_confirmacion_mercado = False
        self.confirmar_mercado_distinto = False
        self.importe_invertir = ""
        self.precio_max = ""
        self.precio_min = ""

    def cancelar_formulario(self):
        self._reset_formulario()
        self.guardado_error = ""
        self.mostrar_formulario = False

    def set_modo_valor(self, value: str | list[str]):
        # `rx.segmented_control.root.on_change` dispara con str | list[str]
        # (mismo motivo que AltaOperacionState.set_modo_valor en
        # alta_operacion_form.py) -- el chequeo de tipos de eventos de
        # Reflex es estricto con la anotación, no basta con que en la
        # práctica siempre llegue un str.
        self.modo_valor = value

    def set_valor_existente(self, value: str):
        self.valor_existente = value

    def set_busqueda_valor_existente(self, value: str):
        self.busqueda_valor_existente = value
        self.valor_existente = ""

    def elegir_valor_existente(self, ticker: str, mercado: str, empresa: str):
        self.valor_existente = f"{ticker} ({mercado}) — {empresa}"
        self.busqueda_valor_existente = ""

    def set_busqueda_texto(self, value: str):
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
        """Con .debounce() en el componente -- ver alta_operacion_form.py."""
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
                f"Ya existe «{ticker}» registrado exactamente en este mercado ({mercado}). "
                "Selecciónalo como valor existente en vez de darlo de alta de nuevo."
            )
            self.requiere_confirmacion_mercado = False
        else:
            mercados = ", ".join(sorted({v["mercado"] for v in existentes}))
            self.advertencia_ticker = (
                f"Ya hay un valor con el ticker «{ticker}» en el catálogo, pero en otro "
                f"mercado ({mercados}). Si es la misma empresa cotizando en un mercado "
                "distinto, confirma abajo para continuar; si ha sido un error, elige "
                "«Valor existente» en su lugar."
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

    def set_importe_invertir(self, value: str):
        self.importe_invertir = value

    def set_precio_max(self, value: str):
        self.precio_max = value

    def set_precio_min(self, value: str):
        self.precio_min = value

    @rx.var
    def resultados_valor_existente(self) -> list[dict]:
        texto = self.busqueda_valor_existente.strip().lower()
        if not texto:
            return []
        coincidencias = [
            v
            for v in self.valores_disponibles_raw
            if texto in v["ticker"].lower() or texto in v["empresa"].lower()
        ]
        coincidencias.sort(key=lambda v: not v["ticker"].lower().startswith(texto))
        return coincidencias[:30]

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

    async def guardar_candidato(self):
        self.guardado_error = ""

        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            self.guardado_error = "Debes iniciar sesión."
            return

        try:
            importe_invertir = float(self.importe_invertir)
            precio_max = float(self.precio_max)
            precio_min = float(self.precio_min) if self.precio_min else None
        except ValueError:
            self.guardado_error = "Revisa los importes numéricos."
            return
        if importe_invertir <= 0 or precio_max <= 0:
            self.guardado_error = "El importe a invertir y el precio máx deben ser mayores que 0."
            return

        if self.modo_valor == "nuevo":
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

        try:
            crear_candidato(
                auth_state.current_user["id"],
                id_valor,
                importe_invertir,
                precio_max,
                precio_min,
                self.TIPO_LISTA,
            )
        except CandidatoDuplicadoError as e:
            self.guardado_error = str(e)
            return

        self.candidatos = obtener_candidatos(auth_state.current_user["id"], self.TIPO_LISTA)
        self._reset_formulario()
        self.mostrar_formulario = False
        await self._recargar_proyeccion()
        return type(self).refrescar_cotizaciones

    def empezar_edicion(self, id_candidato: int, importe: str, precio_max: str, precio_min: str):
        self.editando_id = id_candidato
        self.editando_importe = importe
        self.editando_precio_max = precio_max
        self.editando_precio_min = precio_min
        self.editando_error = ""

    def cancelar_edicion(self):
        self.editando_id = 0
        self.editando_error = ""

    def set_editando_importe(self, value: str):
        self.editando_importe = value

    def set_editando_precio_max(self, value: str):
        self.editando_precio_max = value

    def set_editando_precio_min(self, value: str):
        self.editando_precio_min = value

    async def guardar_edicion(self):
        try:
            importe = float(self.editando_importe)
            precio_max = float(self.editando_precio_max)
            precio_min = float(self.editando_precio_min) if self.editando_precio_min else None
        except ValueError:
            self.editando_error = "Revisa los importes numéricos."
            return
        if importe <= 0 or precio_max <= 0:
            self.editando_error = "El importe a invertir y el precio máx deben ser mayores que 0."
            return

        actualizar_candidato(self.editando_id, importe, precio_max, precio_min)
        self.editando_id = 0
        self.editando_error = ""

        auth_state = await self.get_state(AuthState)
        if auth_state.is_authenticated:
            self.candidatos = obtener_candidatos(auth_state.current_user["id"], self.TIPO_LISTA)
        await self._recargar_proyeccion()

    async def eliminar(self, id_candidato: int):
        eliminar_candidato(id_candidato)
        auth_state = await self.get_state(AuthState)
        if auth_state.is_authenticated:
            self.candidatos = obtener_candidatos(auth_state.current_user["id"], self.TIPO_LISTA)
        await self._recargar_proyeccion()

    async def _recargar_proyeccion(self):
        """El importe a invertir de cada fila de Largo Plazo entra en el
        cálculo del gráfico "Objetivo vs. real aplicando compras" de
        RADAR (punto 6 del encargo, ver states/radar_state.py) -- se
        avisa a ese otro estado cada vez que la lista cambia, para no
        tener que recargar toda la página. La lista de Corto Plazo no
        participa en ese balance (punto 7), así que su subclase pone
        `ACTUALIZA_PROYECCION = False` y este método no hace nada."""
        if not self.ACTUALIZA_PROYECCION:
            return
        from gestion_cartera.states.radar_state import RadarState

        radar_state = await self.get_state(RadarState)
        await radar_state.recargar_proyeccion()


class RadarCandidatoState(_RadarCandidatoMixin, rx.State):
    """Lista de posibles compras de Largo Plazo (punto 4 del encargo) --
    ver el mixin de arriba para toda la lógica."""

    TIPO_LISTA: ClassVar[str] = "Largo Plazo"
    ACTUALIZA_PROYECCION: ClassVar[bool] = True


class RadarCandidatoCortoPlazoState(_RadarCandidatoMixin, rx.State):
    """Segunda lista de posibles compras (punto 7 del encargo): mismo
    mixin que RadarCandidatoState, pero sobre
    `tipo_lista == "Corto Plazo"` y sin efecto en los gráficos de
    balance/reequilibrio (ACTUALIZA_PROYECCION = False). Al combinar el
    mixin con `rx.State` en una clase propia (en vez de heredar
    directamente de RadarCandidatoState), Reflex le da su propio
    almacenamiento independiente para `candidatos`, el formulario de
    alta, la edición inline, etc. -- ver la nota al principio del
    fichero sobre por qué la herencia directa no servía."""

    TIPO_LISTA: ClassVar[str] = "Corto Plazo"
    ACTUALIZA_PROYECCION: ClassVar[bool] = False

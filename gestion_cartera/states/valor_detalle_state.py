"""Estado de la página VALOR: detalle de un único valor dentro de la
cartera seleccionada -- resumen (con TIR individual con y sin
revalorización), rentabilidad por año, operaciones por año y listado
completo de operaciones de ese valor.
"""

import reflex as rx

from gestion_cartera.operaciones_db import obtener_cartera_id, obtener_operaciones_de_valor
from gestion_cartera.services import yahoo_finance
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.valor_db import (
    MERCADOS,
    actualizar_ticker_mercado,
    obtener_operaciones_por_anio,
    obtener_rentabilidad_por_anio,
    obtener_resumen_valor,
)


class ValorDetalleState(rx.State):
    resumen: dict = {}
    rentabilidad_por_anio: list[dict] = []
    operaciones_por_anio: list[dict] = []
    operaciones: list[dict] = []
    no_encontrado: bool = False

    # --- Diálogo "Editar ticker/mercado" ---
    mercados_disponibles: list[str] = MERCADOS
    editar_ticker_open: bool = False
    editando_ticker: str = ""
    editando_mercado: str = ""
    editar_ticker_error: str = ""

    # --- Gráficos de cotización (mensual/anual) ---
    # Se piden a Yahoo Finance en segundo plano (ver cargar_historico)
    # una sola vez, al entrar en la página -- no en cada render ni con
    # un refresco periódico, así que se quedan en caché para el resto
    # de la sesión en esta pestaña hasta que se vuelva a entrar en la
    # página (o se cambie de cartera).
    historico_mensual: list[dict] = []
    historico_anual: list[dict] = []
    cargando_historico: bool = False
    historico_error: str = ""

    async def cargar_datos(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return

        from gestion_cartera.states.portfolio_state import PortfolioState

        portfolio_state = await self.get_state(PortfolioState)
        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )

        id_valor_str = self.router.page.params.get("id_valor", "")
        try:
            id_valor = int(id_valor_str)
        except ValueError:
            id_valor = 0

        self.historico_mensual = []
        self.historico_anual = []
        self.historico_error = ""

        if id_cartera is None or id_valor == 0:
            self.no_encontrado = True
            self.resumen = {}
            return

        resumen = obtener_resumen_valor(id_cartera, id_valor)
        if resumen is None:
            self.no_encontrado = True
            self.resumen = {}
            return

        self.no_encontrado = False
        self.resumen = resumen
        self.rentabilidad_por_anio = obtener_rentabilidad_por_anio(id_cartera, id_valor)
        self.operaciones_por_anio = obtener_operaciones_por_anio(id_cartera, id_valor)
        self.operaciones = obtener_operaciones_de_valor(id_cartera, id_valor)

        return ValorDetalleState.cargar_historico

    @rx.event(background=True)
    async def cargar_historico(self):
        """Trae los históricos de cotización (últimos 30 días y últimos
        12 meses, convertidos a euros) para los dos gráficos de la
        página. Va detrás de `cargar_datos` para que la página se vea
        al instante con lo que ya hay en la base de datos, y los
        gráficos aparezcan un poco después."""
        async with self:
            if self.cargando_historico:
                return
            self.cargando_historico = True
            self.historico_error = ""
            ticker = self.resumen.get("ticker", "")
            mercado = self.resumen.get("mercado")
            moneda = self.resumen.get("moneda", "EUR")

        if not ticker:
            async with self:
                self.cargando_historico = False
            return

        errores = []
        mensual: list[dict] = []
        anual: list[dict] = []
        try:
            mensual = yahoo_finance.obtener_historico(
                ticker, moneda, mercado, periodo="1mo", intervalo="1d", formato_fecha="%d/%m"
            )
        except Exception as e:
            errores.append(f"mensual: {e}")
        try:
            anual = yahoo_finance.obtener_historico(
                ticker, moneda, mercado, periodo="1y", intervalo="1wk", formato_fecha="%m/%Y"
            )
        except Exception as e:
            errores.append(f"anual: {e}")

        async with self:
            self.historico_mensual = mensual
            self.historico_anual = anual
            self.cargando_historico = False
            if errores:
                self.historico_error = (
                    "No se ha podido cargar el histórico de cotización: "
                    + "; ".join(errores)
                )

    # --- Editar ticker/mercado ---
    def abrir_editar_ticker(self):
        self.editando_ticker = self.resumen.get("ticker", "")
        self.editando_mercado = self.resumen.get("mercado", "")
        self.editar_ticker_error = ""
        self.editar_ticker_open = True

    def set_editar_ticker_open(self, value: bool):
        self.editar_ticker_open = value

    def set_editando_ticker(self, value: str):
        self.editando_ticker = value

    def set_editando_mercado(self, value: str):
        self.editando_mercado = value

    async def guardar_ticker_mercado(self):
        ticker = self.editando_ticker.strip().upper()
        if not ticker or not self.editando_mercado:
            self.editar_ticker_error = "Indica el ticker y el mercado."
            return

        id_valor = self.resumen.get("id_valor", 0)
        if not id_valor:
            self.editar_ticker_error = "No se ha encontrado el valor."
            return

        error = actualizar_ticker_mercado(id_valor, ticker, self.editando_mercado)
        if error:
            self.editar_ticker_error = error
            return

        self.editar_ticker_open = False
        await self.cargar_datos()

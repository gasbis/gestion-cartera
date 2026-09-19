"""Estado de la página VALOR: detalle de un único valor dentro de la
cartera seleccionada -- resumen (con TIR individual con y sin
revalorización), rentabilidad por año, operaciones por año y listado
completo de operaciones de ese valor.
"""

import reflex as rx

from gestion_cartera.operaciones_db import obtener_cartera_id, obtener_operaciones_de_valor
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

"""Estado de la página VALOR: detalle de un único valor dentro de la
cartera seleccionada -- resumen (con TIR individual con y sin
revalorización), rentabilidad por año, operaciones por año y listado
completo de operaciones de ese valor.
"""

import reflex as rx

from gestion_cartera.operaciones_db import obtener_cartera_id, obtener_operaciones_de_valor
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.valor_db import (
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

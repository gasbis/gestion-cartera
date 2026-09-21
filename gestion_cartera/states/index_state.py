"""Estado de la página principal (resumen general de la cartera
seleccionada): reutiliza las mismas tenencias/TIR que la página CARTERA
(ver resumen_db.py) para las tarjetas, las tablas top-5, el gráfico de
dividendos por año y los gráficos de distribución por zona/supersector.
"""

import reflex as rx

from gestion_cartera.operaciones_db import obtener_cartera_id
from gestion_cartera.resumen_db import (
    obtener_distribucion_sectores,
    obtener_distribucion_zonas,
    obtener_dividendos_por_anio,
    obtener_dividendos_totales_mostrar,
    obtener_resumen_general,
    obtener_top_valores,
)
from gestion_cartera.states.auth_state import AuthState


def _resumen_vacio() -> dict:
    return {
        "valor_compra_mostrar": "—",
        "valor_mercado_mostrar": "—",
        "saldo_eur_mostrar": "—",
        "saldo_pct_mostrar": "—",
        "color_saldo": "var(--gray-9)",
        "tir_con_mostrar": "—",
        "tir_sin_mostrar": "Sin revalorización: —",
        "color_tir": "var(--gray-9)",
        "numero_valores": 0,
        "fecha_ultima_operacion_mostrar": "—",
    }


def _top_valores_vacio() -> dict[str, list[dict]]:
    return {
        "mejor_revalorizacion": [],
        "peor_revalorizacion": [],
        "mejor_yoc": [],
        "peor_yoc": [],
    }


class ResumenGeneralState(rx.State):
    resumen: dict = _resumen_vacio()
    top_valores: dict[str, list[dict]] = _top_valores_vacio()
    dividendos_por_anio: list[dict] = []
    dividendos_totales_mostrar: str = "—"
    zonas: list[dict] = []
    sectores: list[dict] = []

    async def cargar_datos(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return

        from gestion_cartera.states.portfolio_state import PortfolioState

        portfolio_state = await self.get_state(PortfolioState)
        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )

        if id_cartera is None:
            self.resumen = _resumen_vacio()
            self.top_valores = _top_valores_vacio()
            self.dividendos_por_anio = []
            self.dividendos_totales_mostrar = "—"
            self.zonas = []
            self.sectores = []
            return

        self.resumen = obtener_resumen_general(id_cartera)
        self.top_valores = obtener_top_valores(id_cartera)
        self.dividendos_por_anio = obtener_dividendos_por_anio(id_cartera)
        self.dividendos_totales_mostrar = obtener_dividendos_totales_mostrar(
            self.dividendos_por_anio
        )
        self.zonas = obtener_distribucion_zonas(id_cartera)
        self.sectores = obtener_distribucion_sectores(id_cartera)

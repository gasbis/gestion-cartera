"""Estado del header: nombre del propietario de la cartera, mes/año de
inicio y fecha de la última operación -- se ven en todas las páginas,
dentro de la barra de cartera integrada en el header (ver
components/control_bar.py). Se recarga en el `on_load` de CADA página
(ver gestion_cartera.py) para que quede al día en cualquiera de ellas,
y también al cambiar de cartera desde el selector.
"""

import reflex as rx

from gestion_cartera.operaciones_db import obtener_cartera_id
from gestion_cartera.resumen_db import (
    obtener_fecha_primera_operacion_mostrar,
    obtener_fecha_ultima_operacion,
)
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.states.portfolio_state import PortfolioState


class HeaderState(rx.State):
    nombre_usuario: str = ""
    fecha_inicio_mostrar: str = ""
    fecha_ultima_operacion_mostrar: str = "—"

    async def cargar_datos(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            self.nombre_usuario = ""
            self.fecha_inicio_mostrar = ""
            self.fecha_ultima_operacion_mostrar = "—"
            return

        portfolio_state = await self.get_state(PortfolioState)
        self.nombre_usuario = auth_state.current_user["nombre"]
        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )

        if id_cartera is None:
            self.fecha_inicio_mostrar = ""
            self.fecha_ultima_operacion_mostrar = "—"
            return

        fecha_inicio = obtener_fecha_primera_operacion_mostrar(id_cartera)
        self.fecha_inicio_mostrar = fecha_inicio or ""
        self.fecha_ultima_operacion_mostrar = obtener_fecha_ultima_operacion(id_cartera)

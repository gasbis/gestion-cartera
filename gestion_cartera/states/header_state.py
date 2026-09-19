"""Estado del header: la línea "Propiedad de ... · iniciada en ..." que
se ve en todas las páginas. Se recarga en el `on_load` de CADA página
(ver gestion_cartera.py) para que quede al día en cualquiera de ellas, y
también al cambiar de cartera desde el selector de la página principal.
"""

import reflex as rx

from gestion_cartera.operaciones_db import obtener_cartera_id
from gestion_cartera.resumen_db import obtener_fecha_primera_operacion_mostrar
from gestion_cartera.states.auth_state import AuthState


class HeaderState(rx.State):
    propiedad_mostrar: str = ""

    async def cargar_datos(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            self.propiedad_mostrar = ""
            return

        from gestion_cartera.pages.index import PortfolioState

        portfolio_state = await self.get_state(PortfolioState)
        nombre = auth_state.current_user["nombre"]
        id_cartera = obtener_cartera_id(
            auth_state.current_user["id"], portfolio_state.selected_portfolio
        )

        fecha_inicio = (
            obtener_fecha_primera_operacion_mostrar(id_cartera) if id_cartera is not None else None
        )
        if fecha_inicio is None:
            self.propiedad_mostrar = f"Propiedad de {nombre}"
        else:
            self.propiedad_mostrar = f"Propiedad de {nombre} · iniciada en {fecha_inicio}"

"""Estado de la página IRPF: selector de año fiscal y resumen calculado
para ese año, combinando SIEMPRE las dos carteras del usuario (ver
resumen_irpf_db.obtener_resumen_irpf).
"""

import reflex as rx

from gestion_cartera.irpf_excel import generar_excel_irpf
from gestion_cartera.resumen_irpf_db import obtener_anios_disponibles, obtener_resumen_irpf
from gestion_cartera.states.auth_state import AuthState

# Claves de `obtener_resumen_irpf` que son listados (van en sus propios
# state vars, ver más abajo) -- el resto son los totales/textos ya
# formateados que se muestran en las tarjetas (ver `totales`).
_CLAVES_LISTADOS = ("listado_dividendos", "listado_ventas", "exceso_origen_por_zona")


class IrpfState(rx.State):
    anios_disponibles: list[str] = []
    anio_seleccionado: str = ""

    totales: dict = {}
    listado_dividendos: list[dict] = []
    listado_ventas: list[dict] = []
    exceso_origen_por_zona: list[dict] = []

    # True mientras se (re)calcula el resumen (carga inicial o cambio de
    # año, ambos recorren todo el histórico de operaciones de las dos
    # carteras) -- gatilla el skeleton en vez de las tarjetas en 0/vacías.
    cargando: bool = True

    async def cargar_datos(self):
        self.cargando = True
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            self.cargando = False
            return
        id_usuario = auth_state.current_user["id"]
        self.anios_disponibles = [str(a) for a in obtener_anios_disponibles(id_usuario)]
        if self.anio_seleccionado not in self.anios_disponibles and self.anios_disponibles:
            self.anio_seleccionado = self.anios_disponibles[0]
        self._recalcular(id_usuario)
        self.cargando = False

    async def set_anio_seleccionado(self, value: str):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return
        self.cargando = True
        self.anio_seleccionado = value
        self._recalcular(auth_state.current_user["id"])
        self.cargando = False

    def _recalcular(self, id_usuario: int):
        if not self.anio_seleccionado:
            self.totales = {}
            self.listado_dividendos = []
            self.listado_ventas = []
            self.exceso_origen_por_zona = []
            return

        resumen = obtener_resumen_irpf(id_usuario, int(self.anio_seleccionado))
        self.listado_dividendos = resumen["listado_dividendos"]
        self.listado_ventas = resumen["listado_ventas"]
        self.exceso_origen_por_zona = resumen["exceso_origen_por_zona"]
        self.totales = {k: v for k, v in resumen.items() if k not in _CLAVES_LISTADOS}

    async def descargar_excel(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated or not self.anio_seleccionado:
            return
        anio = int(self.anio_seleccionado)
        datos = generar_excel_irpf(auth_state.current_user["id"], anio)
        return rx.download(
            data=datos,
            filename=f"IRPF_{anio}.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

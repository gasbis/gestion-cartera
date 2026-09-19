"""Estado de la página BROKERS: alta de brokers nuevos (nunca se borran,
para no romper el histórico de operaciones que ya los referencian) y
control de existencias por bróker, agregando las dos carteras."""

import reflex as rx

from gestion_cartera.cartera_db import (
    crear_broker,
    obtener_brokers_con_id,
    obtener_existencias_broker,
)
from gestion_cartera.states.auth_state import AuthState


class BrokersState(rx.State):
    brokers: list[dict] = []
    broker_seleccionado_id: int = 0
    existencias: list[dict] = []

    nombre_nuevo_broker: str = ""
    alta_error: str = ""
    alta_ok: bool = False

    async def cargar_datos(self):
        auth_state = await self.get_state(AuthState)
        if not auth_state.is_authenticated:
            return
        self.brokers = obtener_brokers_con_id()

    def set_nombre_nuevo_broker(self, value: str):
        self.nombre_nuevo_broker = value
        self.alta_error = ""
        self.alta_ok = False

    def dar_alta_broker(self):
        nombre = self.nombre_nuevo_broker.strip()
        if not nombre:
            self.alta_error = "Indica el nombre del bróker."
            return
        if any(b["nombre"].lower() == nombre.lower() for b in self.brokers):
            self.alta_error = f"Ya existe un bróker llamado «{nombre}»."
            return
        nuevo_id = crear_broker(nombre)
        self.brokers = obtener_brokers_con_id()
        self.nombre_nuevo_broker = ""
        self.alta_error = ""
        self.alta_ok = True
        self.broker_seleccionado_id = nuevo_id

    def ver_existencias(self, id_broker: int):
        self.broker_seleccionado_id = id_broker
        self.existencias = obtener_existencias_broker(id_broker)

    @rx.var
    def broker_seleccionado_nombre(self) -> str:
        for b in self.brokers:
            if b["id"] == self.broker_seleccionado_id:
                return b["nombre"]
        return ""

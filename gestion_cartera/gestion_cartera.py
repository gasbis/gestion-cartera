"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from gestion_cartera.pages.index import index
from gestion_cartera.pages.nueva_operacion import nueva_operacion
from gestion_cartera.pages.usuarios import usuarios
from gestion_cartera.components.alta_operacion_form import AltaOperacionState
from gestion_cartera.states.auth_state import AuthState

# Import necesario aunque no se use nada de aquí directamente: es lo que
# hace que `reflex db makemigrations` detecte estas tablas. Sin esta
# línea, Sector/Valor/Operacion/etc. nunca se cargan y el script de
# migración sale vacío (o incompleto) para ellas.
from gestion_cartera import models  # noqa: F401


app = rx.App(
    theme=rx.theme(
        accent_color="blue",
        gray_color="slate",
        radius="medium",
        appearance="light",
    ),
)
app.add_page(
    index,
    route="/",
    title="Bienvenido a Gestión Cartera",
    description="En esta página encontraras un resumen general de tu cartera de inversiones.",
    )
# Ruta temporal solo para poder ver y probar el formulario de alta de
# operación de forma aislada. Cuando montemos la página OPERACIONES de
# verdad (con el listado), esta ruta se sustituirá por la definitiva.
app.add_page(
    nueva_operacion,
    route="/operaciones/nueva",
    title="Nueva operación",
    on_load=AltaOperacionState.cargar_datos_iniciales,
)
app.add_page(
    usuarios,
    route="/usuarios",
    title="Usuarios",
    on_load=AuthState.cargar_usuarios,
)
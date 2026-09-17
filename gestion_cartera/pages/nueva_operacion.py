import reflex as rx

from gestion_cartera.components.alta_operacion_form import alta_operacion_form
from gestion_cartera.components.auth_guard import requiere_login


def nueva_operacion() -> rx.Component:
    return requiere_login(
        rx.container(
            rx.flex(
                alta_operacion_form(),
                justify="center",
                padding="2em",
            ),
            size="4",
        )
    )
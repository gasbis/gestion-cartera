import reflex as rx

from gestion_cartera.components.auth import cambio_password_obligatorio, login_screen
from gestion_cartera.states.auth_state import AuthState


def requiere_login(contenido: rx.Component) -> rx.Component:
    """Envuelve una página: sin sesión → login; con contraseña inicial
    pendiente → pantalla de cambio obligatorio; si no, el contenido real.
    """
    return rx.cond(
        AuthState.is_authenticated,
        rx.cond(AuthState.must_change_password, cambio_password_obligatorio(), contenido),
        login_screen(),
    )
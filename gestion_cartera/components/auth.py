import reflex as rx

from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.styles import SPACE_LG


def campo_login(
    label: str, name: str, tipo: str, error: rx.Var[str] | None = None
) -> rx.Component:
    hijos = [
        rx.text(label, size="2", weight="medium"),
        rx.input(name=name, type=tipo, required=True, width="100%"),
    ]
    if error is not None:
        hijos.append(rx.cond(error != "", rx.text(error, size="1", color="red")))
    return rx.flex(*hijos, direction="column", spacing="1", width="100%")


def tarjeta_centrada(*hijos: rx.Component) -> rx.Component:
    return rx.center(
        rx.card(
            rx.flex(*hijos, direction="column", spacing="4"),
            width="100%",
            max_width="360px",
            padding=SPACE_LG,
        ),
        height="100vh",
        width="100%",
    )


def login_screen() -> rx.Component:
    return tarjeta_centrada(
        rx.heading("Gestión Cartera", size="5"),
        rx.text("Inicia sesión para continuar", size="2", color_scheme="gray"),
        rx.form(
            rx.flex(
                campo_login("Correo electrónico", "email", "email", AuthState.email_error),
                campo_login("Contraseña", "password", "password", AuthState.password_error),
                rx.cond(
                    AuthState.auth_error != "",
                    rx.callout(AuthState.auth_error, color_scheme="red", size="1"),
                ),
                rx.button("Acceder", type="submit", width="100%"),
                direction="column",
                spacing="3",
            ),
            on_submit=AuthState.sign_in,
            reset_on_submit=False,
            width="100%",
        ),
    )


def cambio_password_obligatorio() -> rx.Component:
    """Pantalla completa (no un diálogo descartable): el usuario no puede
    seguir hasta cambiar su contraseña inicial."""
    return tarjeta_centrada(
        rx.heading("Cambia tu contraseña", size="5"),
        rx.text(
            "Por seguridad, debes establecer una contraseña nueva antes de continuar.",
            size="2",
            color_scheme="gray",
        ),
        rx.form(
            rx.flex(
                campo_login(
                    "Contraseña actual",
                    "current_password",
                    "password",
                    AuthState.change_password_current_error,
                ),
                campo_login(
                    "Nueva contraseña",
                    "new_password",
                    "password",
                    AuthState.change_password_new_error,
                ),
                campo_login("Confirmar nueva contraseña", "confirm_password", "password"),
                rx.cond(
                    AuthState.change_password_error != "",
                    rx.callout(AuthState.change_password_error, color_scheme="red", size="1"),
                ),
                rx.button("Guardar contraseña", type="submit", width="100%"),
                direction="column",
                spacing="3",
            ),
            on_submit=AuthState.cambiar_password,
            reset_on_submit=True,
            width="100%",
        ),
    )
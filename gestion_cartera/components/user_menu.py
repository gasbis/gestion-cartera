"""Botón de usuario en el extremo derecho del header: abre un menú con
cambio de contraseña, cambio de nombre de usuario y cierre de sesión.
"""

import reflex as rx

from gestion_cartera.components.auth import campo_login
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.states.header_state import HeaderState


def dialogo_cambiar_password() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Cambiar contraseña"),
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
                    campo_login(
                        "Confirmar nueva contraseña", "confirm_password", "password"
                    ),
                    rx.cond(
                        AuthState.change_password_error != "",
                        rx.callout(
                            AuthState.change_password_error, color_scheme="red", size="1"
                        ),
                    ),
                    rx.hstack(
                        rx.dialog.close(
                            rx.button(
                                "Cancelar",
                                variant="soft",
                                color_scheme="gray",
                                type="button",
                            )
                        ),
                        rx.button("Guardar contraseña", type="submit"),
                        spacing="3",
                        justify="end",
                        width="100%",
                    ),
                    direction="column",
                    spacing="3",
                ),
                on_submit=AuthState.cambiar_password,
                reset_on_submit=True,
            ),
        ),
        open=AuthState.cambiar_password_dialog_open,
        on_open_change=AuthState.set_cambiar_password_dialog_open,
    )


def dialogo_cambiar_nombre() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Cambiar nombre de usuario"),
            rx.form(
                rx.flex(
                    campo_login("Nombre", "nombre", "text", AuthState.nombre_error),
                    rx.hstack(
                        rx.dialog.close(
                            rx.button(
                                "Cancelar",
                                variant="soft",
                                color_scheme="gray",
                                type="button",
                            )
                        ),
                        rx.button("Guardar nombre", type="submit"),
                        spacing="3",
                        justify="end",
                        width="100%",
                    ),
                    direction="column",
                    spacing="3",
                ),
                on_submit=[AuthState.cambiar_nombre, HeaderState.cargar_datos],
                reset_on_submit=False,
            ),
        ),
        open=AuthState.cambiar_nombre_dialog_open,
        on_open_change=AuthState.set_cambiar_nombre_dialog_open,
    )


def user_menu() -> rx.Component:
    return rx.fragment(
        rx.menu.root(
            rx.menu.trigger(
                rx.icon_button(
                    rx.icon(tag="user-cog", size=18),
                    variant="soft",
                    color_scheme="gray",
                    radius="full",
                ),
            ),
            rx.menu.content(
                rx.menu.item(
                    "Cambiar contraseña", on_select=AuthState.abrir_cambiar_password
                ),
                rx.menu.item(
                    "Cambiar nombre de usuario", on_select=AuthState.abrir_cambiar_nombre
                ),
                rx.menu.separator(),
                rx.menu.item(
                    "Cerrar sesión", on_select=AuthState.logout, color_scheme="red"
                ),
            ),
        ),
        dialogo_cambiar_password(),
        dialogo_cambiar_nombre(),
    )

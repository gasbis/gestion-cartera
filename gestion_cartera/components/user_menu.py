"""Botón de usuario en el extremo derecho del header: abre un menú con
cambio de contraseña, cambio de nombre de usuario, número de teléfono
para avisos y cierre de sesión.

Cerrar sesión no tenía ningún botón en la app hasta ahora -- se añade
aquí junto con el resto porque, una vez existe un menú de usuario, es
el sitio natural para él.

El número de teléfono (punto 5 del encargo, avisos de RADAR por SMS --
ver services/twilio_sms.py) es opcional -- si se deja vacío, ese
usuario simplemente no recibe avisos (ver
states/radar_candidato_state.py, refrescar_cotizaciones).
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


def dialogo_cambiar_telefono() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Número de teléfono para avisos (SMS)"),
            rx.text(
                "Se usa para los avisos de RADAR (precio de compra/venta) por SMS. "
                "Formato internacional, con el prefijo del país y sin espacios, p.ej. "
                "+34600000000. Déjalo vacío para no recibir avisos.",
                size="1",
                color_scheme="gray",
                margin_bottom="0.5em",
            ),
            rx.form(
                rx.flex(
                    campo_login(
                        "Número de teléfono",
                        "telefono_avisos",
                        "text",
                        AuthState.telefono_avisos_error,
                        default_value=AuthState.current_user["telefono_avisos"],
                        required=False,
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
                        rx.button("Guardar número", type="submit"),
                        spacing="3",
                        justify="end",
                        width="100%",
                    ),
                    direction="column",
                    spacing="3",
                ),
                on_submit=AuthState.cambiar_telefono_avisos,
                reset_on_submit=False,
            ),
        ),
        open=AuthState.cambiar_telefono_dialog_open,
        on_open_change=AuthState.set_cambiar_telefono_dialog_open,
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
                rx.menu.item(
                    "Número de teléfono (avisos SMS)", on_select=AuthState.abrir_cambiar_telefono
                ),
                rx.menu.separator(),
                rx.menu.item(
                    "Cerrar sesión", on_select=AuthState.logout, color_scheme="red"
                ),
            ),
        ),
        dialogo_cambiar_password(),
        dialogo_cambiar_nombre(),
        dialogo_cambiar_telefono(),
    )

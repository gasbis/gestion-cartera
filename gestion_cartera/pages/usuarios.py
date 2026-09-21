import reflex as rx

from gestion_cartera.components.auth import campo_login
from gestion_cartera.components.auth_guard import requiere_admin
from gestion_cartera.components.header import header
from gestion_cartera.components.page_title import page_title
from gestion_cartera.components.scroll_x import scroll_x
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.styles import SPACE_SM


def fila_usuario(item: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["nombre"]),
        rx.table.cell(item["email"]),
        rx.table.cell(rx.cond(item["activo"], "Activo", "Inactivo")),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    "Restablecer contraseña",
                    on_click=AuthState.abrir_reset_password(item["email"], item["nombre"]),
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.button(
                    rx.cond(item["activo"], "Desactivar", "Activar"),
                    on_click=AuthState.alternar_activo(item["email"]),
                    disabled=AuthState.current_user["email"] == item["email"],
                    size="1",
                    variant="soft",
                ),
                spacing="2",
            )
        ),
    )


def dialogo_reset_password() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Restablecer contraseña"),
            rx.dialog.description(
                f"Vas a poner una contraseña temporal para {AuthState.reset_password_nombre}. "
                "Tendrá que cambiarla por una propia en su próximo inicio de sesión.",
                size="2",
                color_scheme="gray",
            ),
            rx.form(
                rx.flex(
                    campo_login("Contraseña temporal", "password", "password"),
                    rx.cond(
                        AuthState.reset_password_error != "",
                        rx.callout(AuthState.reset_password_error, color_scheme="red", size="1"),
                    ),
                    rx.hstack(
                        rx.dialog.close(
                            rx.button(
                                "Cancelar", variant="soft", color_scheme="gray", type="button"
                            )
                        ),
                        rx.button("Restablecer", type="submit"),
                        spacing="3",
                        justify="end",
                        width="100%",
                    ),
                    direction="column",
                    spacing="3",
                    padding_top=SPACE_SM,
                ),
                on_submit=AuthState.restablecer_password_usuario,
                reset_on_submit=True,
            ),
        ),
        open=AuthState.reset_password_open,
        on_open_change=AuthState.set_reset_password_open,
    )


def dialogo_nuevo_usuario() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Nuevo usuario"),
            rx.form(
                rx.flex(
                    campo_login(
                        "Correo electrónico", "email", "email", AuthState.nuevo_usuario_email_error
                    ),
                    campo_login("Nombre", "nombre", "text"),
                    campo_login("Contraseña inicial", "password", "password"),
                    rx.cond(
                        AuthState.nuevo_usuario_error != "",
                        rx.callout(AuthState.nuevo_usuario_error, color_scheme="red", size="1"),
                    ),
                    rx.hstack(
                        rx.dialog.close(
                            rx.button(
                                "Cancelar", variant="soft", color_scheme="gray", type="button"
                            )
                        ),
                        rx.button("Crear usuario", type="submit"),
                        spacing="3",
                        justify="end",
                        width="100%",
                    ),
                    direction="column",
                    spacing="3",
                ),
                on_submit=AuthState.crear_usuario_nuevo,
                reset_on_submit=True,
            ),
        ),
        open=AuthState.nuevo_usuario_open,
        on_open_change=AuthState.set_nuevo_usuario_open,
    )


def pagina_usuarios() -> rx.Component:
    return rx.container(
        header(),
        rx.flex(
            rx.hstack(
                page_title("Usuarios", "Gestión de accesos a la aplicación."),
                rx.spacer(),
                rx.button("Nuevo usuario", on_click=AuthState.abrir_nuevo_usuario),
                width="100%",
                align="center",
                wrap="wrap",
            ),
            scroll_x(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Nombre"),
                            rx.table.column_header_cell("Correo"),
                            rx.table.column_header_cell("Estado"),
                            rx.table.column_header_cell(""),
                        )
                    ),
                    rx.table.body(rx.foreach(AuthState.usuarios, fila_usuario)),
                    width="100%",
                ),
            ),
            dialogo_nuevo_usuario(),
            dialogo_reset_password(),
            direction="column",
            spacing="4",
            padding="1em",
        ),
        size="4",
    )


def usuarios() -> rx.Component:
    return requiere_admin(pagina_usuarios())
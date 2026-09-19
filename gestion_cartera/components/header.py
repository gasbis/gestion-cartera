import reflex as rx

from gestion_cartera.components.control_bar import control_bar
from gestion_cartera.components.user_menu import user_menu
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.styles import LINK_COLOR

_NAV_ITEMS = [
    ("Inicio", "/", "house"),
    ("Cartera", "/cartera", "briefcase"),
    ("Operaciones", "/operaciones", "arrow-right-left"),
    ("Brókers", "/brokers", "landmark"),
]


def _nav_link(label: str, href: str, icon_tag: str) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.icon(tag=icon_tag, size=16),
            rx.text(label, size="2", weight="medium"),
            spacing="1",
            align="center",
        ),
        href=href,
        underline="none",
        color=LINK_COLOR,
    )


def header(extra_on_portfolio_change: list | None = None) -> rx.Component:
    """Cabecera global: logo/enlace a inicio, menú de navegación con
    iconos, botón de usuario y, debajo, la barra de cartera.

    `extra_on_portfolio_change` es la lista de eventos que debe
    disparar, además de los propios del header, el selector de cartera
    al cambiar -- cada página pasa aquí la recarga de sus propios
    datos (p.ej. `[CarteraState.cargar_datos]`), ya que el selector
    ahora está en el header y se ve en todas las páginas.
    """
    return rx.box(
        rx.hstack(
            rx.link(
                rx.hstack(
                    rx.image(
                        src="/LogoBolsa.png",
                        alt="Logo",
                        width="80px",
                        height="80px",
                    ),
                    rx.heading("Gestión Cartera", size="5"),
                    spacing="3",
                    align="center",
                ),
                href="/",
                underline="none",
            ),
            rx.hstack(
                *[_nav_link(label, href, icon) for label, href, icon in _NAV_ITEMS],
                # "Usuarios" solo se muestra al administrador (ver
                # AuthState.es_admin) -- la página en sí también está
                # bloqueada para el resto (requiere_admin en
                # auth_guard.py), esto es solo para no ofrecer un
                # enlace que va a devolver "acceso restringido".
                rx.cond(AuthState.es_admin, _nav_link("Usuarios", "/usuarios", "users")),
                spacing="4",
                padding_left="1em",
                wrap="wrap",
            ),
            rx.spacer(),
            user_menu(),
            padding="1em",
            width="100%",
            align="center",
            wrap="wrap",
        ),
        control_bar(extra_on_change=extra_on_portfolio_change),
        border_bottom="1px solid var(--gray-a5)",
        width="100%",
        background_color="var(--gray-1)",
        position="sticky",
        top="0",
        z_index="10",
    )

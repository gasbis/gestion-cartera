import reflex as rx

from gestion_cartera.components.control_bar import control_bar
from gestion_cartera.components.user_menu import user_menu
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.styles import SPACE_MD, SPACE_SM

_NAV_ITEMS = [
    ("Inicio", "/", "house"),
    ("Cartera", "/cartera", "briefcase"),
    ("Operaciones", "/operaciones", "arrow-right-left"),
    ("Brókers", "/brokers", "landmark"),
    ("Radar", "/radar", "radar"),
    ("IRPF", "/irpf", "receipt"),
    ("Ayuda", "/ayuda", "circle-help"),
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
        # Color normal/hover vía la clase ".app-link" de assets/theme.css
        # (no color=/_hover= de Reflex): con `rx.link(..., href=...)`,
        # Radix renderiza el enlace en modo `asChild` sobre el <Link> de
        # React Router, y en esa combinación el hover que compila el
        # `_hover` de Reflex no se aplicaba de forma fiable al elemento
        # final. Una clase CSS normal no depende de ese mecanismo.
        class_name="app-link",
    )


def _nav_menu_item(label: str, href: str, icon_tag: str) -> rx.Component:
    """Igual que `_nav_link` pero como entrada de `rx.menu` -- para el
    menú de navegación móvil (ver `_nav_mobile_menu`)."""
    return rx.menu.item(
        rx.hstack(
            rx.icon(tag=icon_tag, size=16),
            rx.text(label),
            spacing="2",
            align="center",
        ),
        on_select=rx.redirect(href),
    )


def _nav_mobile_menu() -> rx.Component:
    """Menú de navegación para pantallas estrechas: un único botón
    hamburguesa que despliega los mismos enlaces que la barra de
    navegación de escritorio (`_NAV_ITEMS`), en vez de mostrarlos todos
    en línea -- eso es lo que hacía que el header ocupara media
    pantalla de alto en móvil, al ir envolviendo enlace tras enlace.
    """
    return rx.box(
        rx.menu.root(
            rx.menu.trigger(
                rx.icon_button(
                    rx.icon(tag="menu", size=18),
                    variant="soft",
                    color_scheme="gray",
                ),
            ),
            rx.menu.content(
                *[_nav_menu_item(label, href, icon) for label, href, icon in _NAV_ITEMS],
                rx.cond(
                    AuthState.es_admin,
                    _nav_menu_item("Usuarios", "/usuarios", "users"),
                ),
            ),
        ),
        display=rx.breakpoints(initial="block", md="none"),
    )


def header(
    extra_on_portfolio_change: list | None = None,
    mostrar_selector_cartera: bool = False,
    etiqueta_fija: str | None = None,
) -> rx.Component:
    """Cabecera global: logo/enlace a inicio, menú de navegación con
    iconos, botón de usuario y, debajo (opcionalmente), la barra de
    cartera.

    `extra_on_portfolio_change` es la lista de eventos que debe
    disparar, además de los propios del header, el selector de cartera
    al cambiar -- cada página pasa aquí la recarga de sus propios
    datos (p.ej. `[CarteraState.cargar_datos]`).

    `mostrar_selector_cartera` controla si aparece la barra de cartera
    (el interruptor Largo/Corto Plazo). Por defecto NO se muestra: solo
    tiene sentido en las páginas que trabajan sobre UNA cartera a la vez
    (Inicio, Cartera, Operaciones) -- el resto de páginas, o bien no usa
    ese dato (Brókers, Usuarios), o bien combina ambas carteras siempre
    (IRPF), o bien trabaja siempre sobre UNA cartera fija sin dejar
    elegir (Radar, siempre Largo Plazo), así que mostrar el interruptor
    ahí sería confuso o directamente engañoso.

    `etiqueta_fija`, si se da, se muestra en el mismo lugar que
    ocuparía la barra de cartera pero como texto simple, sin
    interruptor -- para páginas como Radar, que trabajan siempre sobre
    UNA cartera fija y conviene dejarlo claro igualmente. Se ignora si
    `mostrar_selector_cartera` es True.
    """
    return rx.box(
        rx.hstack(
            rx.link(
                rx.hstack(
                    rx.image(
                        src="/LogoBolsa.png",
                        alt="Logo",
                        width=rx.breakpoints(initial="44px", sm="80px"),
                        height=rx.breakpoints(initial="44px", sm="80px"),
                    ),
                    # En móvil el nombre completo ("Gestión Cartera") no
                    # cabe junto al logo, el menú hamburguesa y el botón
                    # de usuario sin forzar el salto de línea que
                    # queríamos evitar -- se oculta y se deja solo el
                    # logo como enlace a Inicio.
                    rx.heading(
                        "Gestión Cartera",
                        size="5",
                        display=rx.breakpoints(initial="none", sm="block"),
                    ),
                    spacing="3",
                    align="center",
                ),
                href="/",
                underline="none",
            ),
            # Navegación de escritorio: en línea, solo a partir de "md".
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
                display=rx.breakpoints(initial="none", md="flex"),
            ),
            rx.spacer(),
            # Navegación móvil: menú hamburguesa, solo por debajo de "md"
            # (ver _nav_mobile_menu, que ya lleva su propio `display`).
            _nav_mobile_menu(),
            user_menu(),
            padding_x="1em",
            # Menos separación por debajo en los formatos que usan el
            # menú hamburguesa (por debajo de "md"): así la fila del
            # logo/menú/usuario queda más pegada a la barra de cartera
            # justo debajo (ver control_bar.py, que recorta su propio
            # padding superior a juego).
            padding_top="1em",
            padding_bottom=rx.breakpoints(initial="0.5em", md="1em"),
            width="100%",
            align="center",
        ),
        # `mostrar_selector_cartera`/`etiqueta_fija` son parámetros fijos
        # de Python (cada página los pasa como literal, no como Var de
        # estado), así que se resuelven aquí mismo con un if normal, sin
        # necesidad de `rx.cond`.
        (
            control_bar(extra_on_change=extra_on_portfolio_change)
            if mostrar_selector_cartera
            else (
                rx.box(
                    rx.text(etiqueta_fija, weight="medium", size="2"),
                    width="100%",
                    padding_x=SPACE_MD,
                    padding_top=rx.breakpoints(initial="0.25em", md=SPACE_SM),
                    padding_bottom=SPACE_SM,
                    border_bottom="1px solid var(--app-separator)",
                )
                if etiqueta_fija is not None
                else rx.fragment()
            )
        ),
        border_bottom="1px solid var(--app-separator)",
        width="100%",
        background_color="var(--gray-1)",
        position="sticky",
        top="0",
        z_index="10",
    )

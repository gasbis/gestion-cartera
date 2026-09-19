import reflex as rx

from gestion_cartera.states.header_state import HeaderState


def header() -> rx.Component:
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
                rx.link("Inicio", href="/", size="2", weight="medium"),
                rx.link("Cartera", href="/cartera", size="2", weight="medium"),
                rx.link("Operaciones", href="/operaciones", size="2", weight="medium"),
                rx.link("Brókers", href="/brokers", size="2", weight="medium"),
                rx.link("Usuarios", href="/usuarios", size="2", weight="medium"),
                spacing="4",
                padding_left="1em",
            ),
            padding="1em",
            width="100%",
            align="center",
        ),        
        border_bottom="1px solid var(--gray-a5)",
        width="100%",
        background_color="var(--gray-1)",
        position="sticky",
        top="0",
        z_index="10",
    )

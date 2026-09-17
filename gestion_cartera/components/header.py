import reflex as rx

def header() -> rx.Component:
    return rx.hstack(
        rx.image(
            src="/LogoBolsa.png",
            alt="Logo",
            width="48px",
            height="48px",
        ),
        rx.heading("Gestión Cartera", size="5"),
        padding="1em",
        border_bottom="1px solid var(--gray-a5)",
        width="100%",
        background_color="var(--gray-1)",
        position="sticky",
        top="0",
        z_index="10",
        align="center",
    )
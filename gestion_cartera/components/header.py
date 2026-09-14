import reflex as rx

def header() -> rx.Component:
    return rx.hstack(
        rx.image(
            src="/LogoBolsa.png",
            alt="Logo",
            width="100px",
            height="100px",
            margin_right="4",
        ),
        rx.heading("Gestión Cartera", size="4"),
        padding="4",
        border_bottom="1px solid",
        border_color="gray.200",
        width="100%",
    )
"""Título + subtítulo estándar al principio del contenido de cada
página (debajo del header)."""

import reflex as rx


def page_title(title: str, subtitle: str) -> rx.Component:
    return rx.flex(
        rx.heading(title, size="6"),
        rx.text(subtitle, size="2", color_scheme="gray"),
        direction="column",
        spacing="1",
    )

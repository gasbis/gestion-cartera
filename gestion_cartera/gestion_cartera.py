"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from gestion_cartera.pages.index import index





app = rx.App()
app.add_page(
    index,
    route="/",
    title="Bienvenido a Gestión Cartera",
    description="En esta página encontraras un resumen general de tu cartera de inversiones.",
    )

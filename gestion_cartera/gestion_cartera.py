"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from gestion_cartera.pages.brokers import brokers
from gestion_cartera.pages.cartera import cartera
from gestion_cartera.pages.index import index
from gestion_cartera.pages.operaciones import operaciones
from gestion_cartera.pages.usuarios import usuarios
from gestion_cartera.pages.valor_detalle import valor_detalle
from gestion_cartera.states.brokers_state import BrokersState
from gestion_cartera.states.cartera_state import CarteraState
from gestion_cartera.states.header_state import HeaderState
from gestion_cartera.states.index_state import ResumenGeneralState
from gestion_cartera.states.operaciones_state import OperacionesState
from gestion_cartera.states.valor_detalle_state import ValorDetalleState
from gestion_cartera.states.auth_state import AuthState

# Import necesario aunque no se use nada de aquí directamente: es lo que
# hace que `reflex db makemigrations` detecte estas tablas. Sin esta
# línea, Sector/Valor/Operacion/etc. nunca se cargan y el script de
# migración sale vacío (o incompleto) para ellas.
from gestion_cartera import models  # noqa: F401


app = rx.App(
    html_lang="es",
    theme=rx.theme(        
        accent_color="indigo",
        gray_color="slate",
        radius="medium",
        appearance="dark",
    ),
    stylesheets=["/theme.css"],
)

app.add_page(
    index,
    route="/",
    title="Bienvenido a Gestión Cartera",
    description="En esta página encontraras un resumen general de tu cartera de inversiones.",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[ResumenGeneralState.cargar_datos, HeaderState.cargar_datos],
    )

app.add_page(
    cartera,
    route="/cartera",
    title="Cartera",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[CarteraState.cargar_datos, HeaderState.cargar_datos],
)
app.add_page(
    operaciones,
    route="/operaciones",
    title="Operaciones",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[OperacionesState.cargar_datos, HeaderState.cargar_datos],
)

app.add_page(
    brokers,
    route="/brokers",
    title="Brokers",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[BrokersState.cargar_datos, HeaderState.cargar_datos],
)

app.add_page(
    usuarios,
    route="/usuarios",
    title="Usuarios",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[AuthState.cargar_usuarios, HeaderState.cargar_datos],
)

app.add_page(
    valor_detalle,
    route="/valor/[id_valor]",
    title="Detalle de valor",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[ValorDetalleState.cargar_datos, HeaderState.cargar_datos],
)

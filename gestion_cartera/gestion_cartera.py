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
    theme=rx.theme(
        # Índigo en vez de azul: mismo espíritu, más denso/oscuro (ver
        # conversación sobre el tema oscuro). Los tonos exactos de fondo
        # (--gray-1/2) y texto (--gray-11/12) se sobrescriben en
        # assets/theme.css; el gray_color="slate" de aquí sigue marcando
        # los pasos intermedios (bordes, hover) que ese CSS no toca.
        accent_color="indigo",
        gray_color="slate",
        radius="medium",
        appearance="dark",
    ),
    # Fija el tema oscuro (fondo en dos tonos de casi negro, texto en dos
    # tonos de casi blanco) -- ver assets/theme.css.
    stylesheets=["/theme.css"],
)
app.add_page(
    index,
    route="/",
    title="Bienvenido a Gestión Cartera",
    description="En esta página encontraras un resumen general de tu cartera de inversiones.",
    on_load=[ResumenGeneralState.cargar_datos, HeaderState.cargar_datos],
    )
app.add_page(
    cartera,
    route="/cartera",
    title="Cartera",
    on_load=[CarteraState.cargar_datos, HeaderState.cargar_datos],
)
app.add_page(
    operaciones,
    route="/operaciones",
    title="Operaciones",
    on_load=[OperacionesState.cargar_datos, HeaderState.cargar_datos],
)
app.add_page(
    brokers,
    route="/brokers",
    title="Brokers",
    on_load=[BrokersState.cargar_datos, HeaderState.cargar_datos],
)
app.add_page(
    usuarios,
    route="/usuarios",
    title="Usuarios",
    on_load=[AuthState.cargar_usuarios, HeaderState.cargar_datos],
)
app.add_page(
    valor_detalle,
    route="/valor/[id_valor]",
    title="Detalle de valor",
    on_load=[ValorDetalleState.cargar_datos, HeaderState.cargar_datos],
)

"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from gestion_cartera.pages.ayuda import ayuda
from gestion_cartera.pages.brokers import brokers
from gestion_cartera.pages.cartera import cartera
from gestion_cartera.pages.index import index
from gestion_cartera.pages.irpf import irpf
from gestion_cartera.pages.operaciones import operaciones
from gestion_cartera.pages.radar import radar
from gestion_cartera.pages.usuarios import usuarios
from gestion_cartera.pages.valor_detalle import valor_detalle
from gestion_cartera.states.brokers_state import BrokersState
from gestion_cartera.states.cartera_state import CarteraState
from gestion_cartera.states.header_state import HeaderState
from gestion_cartera.states.index_state import ResumenGeneralState
from gestion_cartera.states.irpf_state import IrpfState
from gestion_cartera.states.operaciones_state import OperacionesState
from gestion_cartera.states.radar_candidato_state import (
    RadarCandidatoCortoPlazoState,
    RadarCandidatoState,
)
from gestion_cartera.states.radar_state import RadarState
from gestion_cartera.states.valor_detalle_state import ValorDetalleState
from gestion_cartera.states.auth_state import AuthState
from gestion_cartera.services.radar_scheduler import tarea_radar_en_segundo_plano

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
    # Por defecto Reflex solo añade un <meta property="og:image">
    # apuntando a favicon.ico -- eso vale para la pestaña del navegador,
    # pero "Añadir a pantalla de inicio" en móvil/tablet no lo usa:
    # iOS busca específicamente un <link rel="apple-touch-icon">, y
    # Android/Chrome un manifest.json con sus propios iconos. Sin esto
    # dos, el acceso directo sale sin icono (o con una captura genérica
    # de la página). Los PNG e icon-192/512 viven en assets/, generados
    # a partir de LogoBolsa.png.
    head_components=[
        rx.el.link(rel="icon", href="/favicon.ico"),
        rx.el.link(rel="apple-touch-icon", href="/apple-touch-icon.png", sizes="180x180"),
        rx.el.link(rel="manifest", href="/manifest.json"),
        rx.el.meta(name="theme-color", content="#0c151d"),
        # PWA instalable (punto 1 de "convertir esto en app de móvil"):
        # lo de arriba (manifest + iconos) ya deja instalar la app en
        # Android desde Chrome. Estos tres meta van dirigidos solo a
        # iOS/Safari, que hasta hace poco ignoraba el manifest para
        # "Añadir a pantalla de inicio" y en su lugar usaba sus propias
        # etiquetas: sin ellas, Safari abre la PWA dentro de su propia
        # barra de navegador en vez de a pantalla completa.
        rx.el.meta(name="apple-mobile-web-app-capable", content="yes"),
        rx.el.meta(name="apple-mobile-web-app-status-bar-style", content="black-translucent"),
        rx.el.meta(name="apple-mobile-web-app-title", content="Cartera"),
        # Registra el service worker (assets/sw.js) que permite "instalar"
        # la app -- ver ese archivo para por qué NO cachea nada más que
        # unos pocos archivos estáticos (iconos, manifest, theme.css):
        # esto es una app de cartera de valores, y enseñar cifras
        # desactualizadas en modo offline sería peor que no funcionar.
        rx.script(
            """
            if ("serviceWorker" in navigator) {
              window.addEventListener("load", () => {
                navigator.serviceWorker.register("/sw.js");
              });
            }
            """
        ),
    ],
)

# Chequeo automático de RADAR en segundo plano (punto 5 del encargo,
# ver services/radar_scheduler.py): corre solo, cada hora dentro del
# horario de mercado, sin depender de que nadie tenga /radar abierta.
app.register_lifespan_task(tarea_radar_en_segundo_plano)

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

app.add_page(
    radar,
    route="/radar",
    title="Radar",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[
        RadarState.cargar_datos,
        RadarCandidatoState.cargar_datos,
        RadarCandidatoCortoPlazoState.cargar_datos,
        HeaderState.cargar_datos,
    ],
)

app.add_page(
    irpf,
    route="/irpf",
    title="IRPF",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[IrpfState.cargar_datos, HeaderState.cargar_datos],
)

app.add_page(
    ayuda,
    route="/ayuda",
    title="Ayuda",
    description="Qué efecto tiene cada operación y cómo se calculan el coste, la "
    "rentabilidad y el resumen de IRPF.",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
    on_load=[HeaderState.cargar_datos],
)

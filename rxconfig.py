import os

from dotenv import load_dotenv
load_dotenv()
import reflex as rx


def _resolver_db_url() -> str:
    """En Railway (o cualquier otro sitio con un Postgres gestionado) la
    cadena de conexión llega en la variable de entorno DATABASE_URL. En
    local, si no está definida, se sigue usando el SQLite de siempre
    para poder desarrollar sin tener que montar nada.

    Se fuerza el driver psycopg (v3, no psycopg2): tiene wheels
    precompilados más al día, importante porque este proyecto pide
    Python 3.14+. SQLAlchemy no lo elige por defecto aunque esté
    instalado -- hay que indicárselo explícitamente con el prefijo
    `postgresql+psycopg://`. Railway (y algún proveedor heredado del
    estilo Heroku) puede dar la URL como `postgres://` o
    `postgresql://`; ambas se normalizan aquí.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return "sqlite:///reflex.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


config = rx.Config(
    app_name="gestion_cartera",
    show_built_with_reflex=False,
    db_url=_resolver_db_url(),
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ]
)
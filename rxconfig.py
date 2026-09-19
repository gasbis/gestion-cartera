from dotenv import load_dotenv
load_dotenv()
import reflex as rx

config = rx.Config(
    app_name="gestion_cartera",
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ]
)
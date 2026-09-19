"""Estado de selección de cartera (Largo Plazo / Corto Plazo).

Vive en su propio módulo -- no en pages/index.py -- porque el selector
de cartera ahora forma parte del header y se muestra en todas las
páginas (ver components/control_bar.py). Así se puede importar aquí
de forma directa sin crear un import circular con pages/index.py (que
importa components/header.py). El resto de states lo siguen
importando de forma diferida (dentro de sus métodos) para no arrastrar
el árbol completo de páginas al arrancar -- eso no cambia con esta
reubicación, solo cambia de dónde se importa.
"""

import reflex as rx


class PortfolioState(rx.State):
    """Estado de selección de cartera, compartido por toda la app.

    Es el único sitio donde se elige la cartera (Largo Plazo / Corto
    Plazo): el resto de páginas leen `selected_portfolio` de aquí (ver
    `cargar_datos` en cada state), así que el valor persiste al
    navegar entre páginas sin volver a preguntarlo.
    """

    PORTFOLIOS: list[str] = ["Largo Plazo", "Corto Plazo"]

    selected_portfolio: str = "Largo Plazo"

    def set_portfolio(self, portfolio: str):
        self.selected_portfolio = portfolio

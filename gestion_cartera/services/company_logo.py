"""Logo de la empresa para la página de detalle de un valor.

Logo.dev
(https://www.logo.dev/docs/logo-images/introduction), con la clave
pública ("publishable key", pensada para ir en el propio frontend/
código, no es secreta) de Gabriel.

Se consulta por TICKER (con el mismo sufijo de mercado que usamos para
Yahoo Finance, ver `SUFIJO_YAHOO` en services/yahoo_finance.py) en vez
de por nombre de empresa: más preciso, sin ambigüedad entre compañías
con nombres parecidos.

No hace falta ninguna llamada de red aquí -- solo se construye la URL,
y es el propio `<img>` en el navegador el que la carga. Logo.dev nunca
devuelve un error si no encuentra el logo real: sirve un monograma en
su lugar (`fallback=monogram`, el comportamiento por defecto), así que
la imagen SIEMPRE puede mostrarse, no hace falta gestionar el caso
"sin logo".
"""

from urllib.parse import quote

# Mismo mapeo que SUFIJO_YAHOO (services/yahoo_finance.py): el sufijo
# de ticker que usa Logo.dev sigue la misma convención (p.ej.
# "AAPL.L" para Londres, según su propia documentación) que ya usamos
# para consultar la cotización en Yahoo Finance.
_SUFIJO_TICKER = {
    "BME": ".MC",
    "LON": ".L",
    "AMS": ".AS",
    "EPA": ".PA",
    "ETR": ".DE",
    "NASDAQ": "",
    "NYSE": "",
}

_TOKEN = "pk_WnFYZcJ3RGOWg62HgKT2pA"


def obtener_logo_url(ticker: str, mercado: str | None) -> str:
    """URL del logo de `ticker` (con el sufijo de mercado que le
    corresponda). Nunca vacío: si Logo.dev no tiene el logo real,
    sirve un monograma en su lugar."""
    sufijo = _SUFIJO_TICKER.get(mercado or "", "")
    simbolo = quote(f"{ticker}{sufijo}", safe="")
    return (
        f"https://img.logo.dev/ticker/{simbolo}"
        f"?token={_TOKEN}&size=128&format=png&theme=dark&retina=true"
    )

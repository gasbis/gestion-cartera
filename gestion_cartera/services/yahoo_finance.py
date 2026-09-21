"""Cliente mínimo para Yahoo Finance (vía la librería `yfinance`), usado
para refrescar las cotizaciones de la página CARTERA.

Sustituye a Twelve Data para esto porque su plan gratuito no cubre
mercados europeos.
Twelve Data se sigue usando para el buscador de "dar de alta un valor
nuevo" (services/twelvedata.py, buscar_simbolo).
"""

from datetime import datetime, timezone

import yfinance as yf

#PAra traducir las anotaciones de la antigua aplicación
SUFIJO_YAHOO = {
    "BME": ".MC",  # Madrid
    "LON": ".L",  # Londres
    "AMS": ".AS",  # Ámsterdam
    "EPA": ".PA",  # París
    "ETR": ".DE",  # Fráncfort (Xetra)
    "NASDAQ": "",
    "NYSE": "",
}


def _ticker_yahoo(ticker: str, mercado: str | None) -> str:
    sufijo = SUFIJO_YAHOO.get(mercado or "", "")
    return f"{ticker}{sufijo}"


def obtener_cotizacion(ticker: str, moneda_origen: str, mercado: str | None = None) -> dict:
    """Igual que twelvedata.obtener_cotizacion (mismo dict de salida, para
    poder usarse como sustituto directo): precio actual de `ticker` en su
    divisa original y su equivalente en euros.

    `mercado` es nuestro Valor.mercado (BME, NASDAQ...); se traduce al
    sufijo que espera Yahoo Finance (ver SUFIJO_YAHOO). Si el mercado no
    está en el mapeo, se consulta el ticker tal cual, sin sufijo.
    """
    simbolo = _ticker_yahoo(ticker, mercado)
    info = yf.Ticker(simbolo).fast_info

    precio_divisa = info.last_price
    if precio_divisa is None:
        raise RuntimeError(f"Yahoo Finance no devolvió precio para «{simbolo}».")
    precio_divisa = float(precio_divisa)

    # Las acciones de Londres (LON/.L) cotizan en Yahoo Finance en peniques
    # (divisa "GBp", con p minúscula -- distinto de "GBP"), no en libras.
    # Sin este ajuste, el precio saldría 100 veces más alto de lo real al
    # convertirlo con el cambio GBP/EUR.
    if (info.currency or "") in ("GBp", "GBX"):
        precio_divisa /= 100

    if moneda_origen.upper() == "EUR":
        precio_eur = precio_divisa
    else:
        par = f"{moneda_origen.upper()}EUR=X"
        cambio = yf.Ticker(par).fast_info.last_price
        if cambio is None:
            raise RuntimeError(f"Yahoo Finance no devolvió el cambio «{par}».")
        precio_eur = precio_divisa * float(cambio)

    return {
        "cotizacion_divisa": precio_divisa,
        "cotizacion_eur": round(precio_eur, 4),
        "actualizada_en": datetime.now(timezone.utc),
        "llamadas": 1 if moneda_origen.upper() == "EUR" else 2,
    }

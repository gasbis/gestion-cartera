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


def obtener_historico(
    ticker: str,
    moneda_origen: str,
    mercado: str | None = None,
    periodo: str = "1mo",
    intervalo: str = "1d",
    formato_fecha: str = "%d/%m",
) -> list[dict]:
    """Serie histórica de cierres de `ticker`, convertida a euros -- para
    los gráficos de cotización mensual/anual de la página VALOR (ver
    states/valor_detalle_state.py).

    `periodo`/`intervalo` son los mismos códigos que acepta yfinance
    (p.ej. periodo="1mo" intervalo="1d" para un mes de cierres diarios,
    periodo="1y" intervalo="1wk" para un año de cierres semanales).

    Para convertir a euros se pide también el histórico del cambio de
    divisa (mismo periodo/intervalo) y se cruza por fecha -- a
    diferencia de `obtener_cotizacion`, aquí el cambio SÍ varía punto a
    punto (no tendría sentido aplicar el cambio de HOY a un precio de
    hace un año).

    Devuelve una lista de {"fecha": str, "precio": float} (vacía si
    Yahoo Finance no tiene datos para ese símbolo/periodo). El orden es
    cronológico, el más antiguo primero.
    """
    simbolo = _ticker_yahoo(ticker, mercado)
    ticker_yf = yf.Ticker(simbolo)
    historico = ticker_yf.history(period=periodo, interval=intervalo)
    if historico.empty:
        return []

    precios = historico["Close"].astype(float)

    if (ticker_yf.fast_info.currency or "") in ("GBp", "GBX"):
        precios = precios / 100

    if moneda_origen.upper() == "EUR":
        precios_eur = precios
    else:
        par = f"{moneda_origen.upper()}EUR=X"
        cambio = yf.Ticker(par).history(period=periodo, interval=intervalo)["Close"]
        if cambio.empty:
            raise RuntimeError(f"Yahoo Finance no devolvió el histórico de cambio «{par}».")
        # Las dos series pueden no traer exactamente las mismas fechas
        # (festivos distintos entre la bolsa y el mercado de divisas) --
        # se reindexa el cambio a las fechas de los precios, rellenando
        # con el valor más reciente anterior (y el más próximo si el
        # primer punto no tiene cambio previo).
        cambio = cambio.reindex(precios.index, method="ffill").bfill()
        precios_eur = precios * cambio

    return [
        {"fecha": fecha.strftime(formato_fecha), "precio": round(float(p), 4)}
        for fecha, p in precios_eur.items()
    ]

"""Cliente mínimo para Yahoo Finance (vía la librería `yfinance`), usado
para refrescar las cotizaciones de la página CARTERA.

Sustituye a Twelve Data para esto porque su plan gratuito no cubre
mercados europeos.
Twelve Data se sigue usando para el buscador de "dar de alta un valor
nuevo" (services/twelvedata.py, buscar_simbolo).
"""

from datetime import date, datetime, timedelta, timezone

import yfinance as yf

# Valor.mercado -> sufijo del ticker en Yahoo Finance. Las primeras
# claves vienen de la antigua aplicación; el resto son los códigos que
# asigna el buscador de valores nuevos (ver
# services/twelvedata.MIC_A_MERCADO) para las demás bolsas de la zona
# euro. Un mercado que NO esté aquí ya no se consulta "tal cual", sin
# sufijo: con un ticker como TRN (Terna, en Milán) eso devolvía en
# silencio la cotización de OTRA empresa (Trinity Industries, en Nueva
# York). Ver `_ticker_yahoo`.
SUFIJO_YAHOO = {
    "BME": ".MC",  # Madrid
    "LON": ".L",  # Londres
    "AMS": ".AS",  # Ámsterdam
    "EPA": ".PA",  # París
    "ETR": ".DE",  # Fráncfort (Xetra)
    "XETR": ".DE",  # Fráncfort (Xetra), código que da Twelve Data
    "FSX": ".F",  # Fráncfort (parqué)
    "MIL": ".MI",  # Milán
    "EBR": ".BR",  # Bruselas
    "ELI": ".LS",  # Lisboa
    "ISE": ".IR",  # Dublín
    "HEL": ".HE",  # Helsinki
    "VIE": ".VI",  # Viena
    "NASDAQ": "",
    "NYSE": "",
}


class MercadoNoSoportadoError(RuntimeError):
    """El Valor tiene un mercado que la app no sabe traducir a Yahoo
    Finance. Se corrige desde el detalle del valor (editar ticker y
    mercado)."""


def _ticker_yahoo(ticker: str, mercado: str | None) -> str:
    """Símbolo de Yahoo para `ticker` en `mercado`. Sin mercado (valores
    antiguos) se usa el ticker tal cual; con un mercado desconocido se
    lanza MercadoNoSoportadoError en vez de adivinar."""
    if not mercado:
        return ticker
    if mercado not in SUFIJO_YAHOO:
        raise MercadoNoSoportadoError(
            f"Mercado «{mercado}» no soportado para «{ticker}»: elige uno de la lista "
            "en el detalle del valor (editar ticker y mercado)."
        )
    return f"{ticker}{SUFIJO_YAHOO[mercado]}"


def _comprobar_divisa(simbolo: str, divisa_yahoo: str, moneda_origen: str) -> None:
    """Segunda red de seguridad: si Yahoo cotiza el símbolo en otra
    divisa que la del Valor, casi seguro es otra empresa con el mismo
    ticker en otra bolsa -- mejor no guardar un precio que no es."""
    divisa = "GBP" if divisa_yahoo in ("GBp", "GBX") else (divisa_yahoo or "").upper()
    if divisa and moneda_origen and divisa != moneda_origen.upper():
        raise RuntimeError(
            f"Yahoo Finance cotiza «{simbolo}» en {divisa}, no en {moneda_origen.upper()}: "
            "revisa el ticker y el mercado del valor."
        )


def obtener_cotizacion(ticker: str, moneda_origen: str, mercado: str | None = None) -> dict:
    """Igual que twelvedata.obtener_cotizacion (mismo dict de salida, para
    poder usarse como sustituto directo): precio actual de `ticker` en su
    divisa original y su equivalente en euros.

    `mercado` es nuestro Valor.mercado (BME, NASDAQ...); se traduce al
    sufijo que espera Yahoo Finance (ver SUFIJO_YAHOO). Si el mercado no
    está en el mapeo, o Yahoo lo cotiza en otra divisa, lanza un error
    en vez de guardar el precio de otra empresa.
    """
    simbolo = _ticker_yahoo(ticker, mercado)
    info = yf.Ticker(simbolo).fast_info
    _comprobar_divisa(simbolo, info.currency or "", moneda_origen)

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



def _serie_diaria_eur(
    ticker: str,
    moneda_origen: str,
    mercado: str | None,
    desde: date,
    hasta: date,
):
    """Cierres DIARIOS de `ticker` entre `desde` y `hasta` (incluidos),
    en euros y sin el ajuste por splits posteriores -- base común de
    `obtener_cierre_eur` (un día) y `obtener_cierres_mensuales_eur`
    (fin de cada mes). Devuelve una pandas.Series indexada por fecha
    (datetime.date), o None si Yahoo no tiene datos.

    Yahoo Finance devuelve los cierres antiguos ya AJUSTADOS por los
    splits posteriores (el cierre de 2020 de un valor que hizo un split
    1→10 en 2025 aparece dividido entre 10). Aquí se deshace ese ajuste
    multiplicando cada cierre por el producto de los splits posteriores
    a su fecha, para obtener el precio que realmente tenía el título ese
    día: el que corresponde a los títulos que se tenían ENTONCES (la app
    registra el split como una operación aparte, en su fecha)."""
    simbolo = _ticker_yahoo(ticker, mercado)
    ticker_yf = yf.Ticker(simbolo)
    # Hasta hoy (no solo hasta `hasta`): hacen falta los splits
    # posteriores para deshacer su ajuste.
    historico = ticker_yf.history(
        start=desde - timedelta(days=10),
        end=date.today() + timedelta(days=1),
        auto_adjust=False,
        actions=True,
    )
    if historico.empty:
        return None

    cierres = historico["Close"].astype(float).copy()
    cierres.index = [f.date() for f in historico.index]
    cierres = cierres[~cierres.index.duplicated(keep="last")]

    if "Stock Splits" in historico:
        splits = historico["Stock Splits"].astype(float).copy()
        splits.index = [f.date() for f in historico.index]
        splits = splits.groupby(level=0).max()
        factor = 1.0
        factores = {}
        for f in sorted(cierres.index, reverse=True):
            factores[f] = factor
            s = splits.get(f, 0.0)
            if s and s > 0:
                factor *= s
        cierres = cierres * [factores[f] for f in cierres.index]

    try:
        divisa_yahoo = ticker_yf.fast_info.currency or ""
    except Exception:
        divisa_yahoo = ""
    _comprobar_divisa(simbolo, divisa_yahoo, moneda_origen)
    if divisa_yahoo in ("GBp", "GBX"):
        cierres = cierres / 100

    cierres = cierres[(cierres.index >= desde - timedelta(days=10)) & (cierres.index <= hasta)]
    if cierres.empty:
        return None

    if moneda_origen.upper() != "EUR":
        par = f"{moneda_origen.upper()}EUR=X"
        historico_cambio = yf.Ticker(par).history(
            start=desde - timedelta(days=10), end=hasta + timedelta(days=1)
        )
        if historico_cambio.empty:
            return None
        cambio = historico_cambio["Close"].astype(float).copy()
        cambio.index = [f.date() for f in historico_cambio.index]
        cambio = cambio[~cambio.index.duplicated(keep="last")]
        # Festivos distintos entre bolsa y divisas: el cambio más
        # reciente anterior (o el más próximo, al principio).
        cambio = cambio.reindex(sorted(set(cambio.index) | set(cierres.index))).ffill().bfill()
        cierres = cierres * cambio.reindex(cierres.index)

    return cierres.dropna()


def obtener_cierre_eur(
    ticker: str,
    moneda_origen: str,
    mercado: str | None,
    fecha: date,
) -> float | None:
    """Cotización de cierre de `ticker` el día `fecha` (o el último día
    con sesión anterior, si ese día no hubo mercado), en euros y sin
    ajuste por splits posteriores -- para valorar los títulos recibidos
    en un Script (ver dividendos_scrip.valorar_script). None si Yahoo no
    tiene datos para ese símbolo o esa fecha."""
    serie = _serie_diaria_eur(ticker, moneda_origen, mercado, fecha, fecha)
    if serie is None:
        return None
    serie = serie[serie.index <= fecha]
    return float(serie.iloc[-1]) if not serie.empty else None



def obtener_cierres_diarios_eur(
    ticker: str,
    moneda_origen: str,
    mercado: str | None,
    desde: date,
    hasta: date,
) -> dict[date, float]:
    """{fecha: cierre en euros} de cada sesión entre `desde` y `hasta`
    (incluidos) con datos en Yahoo -- ver models.CierreDiario."""
    serie = _serie_diaria_eur(ticker, moneda_origen, mercado, desde, hasta)
    if serie is None:
        return {}
    return {f: float(c) for f, c in serie.items() if desde <= f <= hasta}

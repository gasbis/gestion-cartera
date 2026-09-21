"""Cliente mínimo para la API de Twelve Data (https://twelvedata.com).

Solo dos funciones, que son las dos cosas que necesitamos:
- buscar_simbolo(texto): autocompletar al dar de alta un valor nuevo.
- obtener_cotizacion(ticker, moneda): refrescar el precio cacheado de un
  Valor (ver Valor.cotizacion_divisa / cotizacion_eur en models.py).
"""

import os
from datetime import datetime, timezone

import httpx

BASE_URL = "https://api.twelvedata.com"


def _api_key() -> str:
    key = os.environ.get("TWELVEDATA_API_KEY")
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno TWELVEDATA_API_KEY. "
        )
    return key


def buscar_simbolo(texto: str, limite: int = 5) -> list[dict]:
    """Busca símbolos que coincidan con `texto` (nombre o ticker parcial).

    Devuelve una lista de dicts con: symbol, instrument_name, exchange,
    mic_code, country, currency. Pensado para alimentar el autocompletado
    del sub-formulario "dar de alta un valor nuevo".
    """
    if not texto:
        return []

    respuesta = httpx.get(
        f"{BASE_URL}/symbol_search",
        params={"symbol": texto, "apikey": _api_key()},
        timeout=10,
    )
    respuesta.raise_for_status()
    cuerpo = respuesta.json()

    if cuerpo.get("status") == "error":
        raise RuntimeError(cuerpo.get("message", "Error desconocido de Twelve Data"))

    resultados = cuerpo.get("data", [])[:limite]
    return [
        {
            "ticker": r["symbol"],
            "empresa": r["instrument_name"],
            "bolsa": r["exchange"],
            "mic_code": r.get("mic_code", ""),
            "pais": r.get("country", ""),
            "moneda": r.get("currency", ""),
        }
        for r in resultados
    ]


def _pedir_precio(ticker: str, key: str, mercado: str | None) -> dict:
    """Una llamada a /price. Si se pasa `mercado` y Twelve Data responde
    404 para esa combinación símbolo+exchange concreta (pasa con algunos
    valores: el nombre de "exchange" que devuelve symbol_search no
    siempre es el que espera /price), se reintenta una vez sin el
    parámetro `exchange`, dejando que Twelve Data resuelva el símbolo por
    su cuenta."""
    params = {"symbol": ticker, "apikey": key}
    if mercado:
        params["exchange"] = mercado

    respuesta = httpx.get(f"{BASE_URL}/price", params=params, timeout=10)

    if respuesta.status_code == 404 and mercado:
        respuesta = httpx.get(
            f"{BASE_URL}/price", params={"symbol": ticker, "apikey": key}, timeout=10
        )

    respuesta.raise_for_status()
    return respuesta.json()


def obtener_cotizacion(ticker: str, moneda_origen: str, mercado: str | None = None) -> dict:
    """Devuelve el precio actual de `ticker` en su divisa original y su
    equivalente en euros.

    `moneda_origen` es la divisa del valor (p.ej. "USD"), tal como la
    devolvió buscar_simbolo() al darlo de alta — así evitamos tener que
    volver a preguntarle a la API qué divisa usa cada vez.

    `mercado` es el "exchange" de Twelve Data (p.ej. "NASDAQ", "BME"...),
    tal como lo guardamos en Valor.mercado. Es opcional pero conviene
    pasarlo siempre que se tenga: sin él, un ticker que cotiza en más de
    un mercado (el motivo por el que existe ese campo, ver Valor.mercado
    en models.py) podría devolver el precio del mercado equivocado. Si
    Twelve Data no reconoce esa combinación concreta, se reintenta sin él
    (ver `_pedir_precio`).

    Devuelve: {"cotizacion_divisa": float, "cotizacion_eur": float,
    "actualizada_en": datetime, "llamadas": int}. `llamadas` es cuántas
    peticiones HTTP ha hecho en total esta llamada (1 o 2: hace una
    segunda a /exchange_rate solo si la moneda no es EUR) -- lo necesita
    quien la invoque en bucle para espaciar las peticiones y no superar
    el límite de 8/minuto del plan gratuito. Si la moneda ya es EUR, no
    hace esa segunda llamada.
    """
    key = _api_key()

    cuerpo_precio = _pedir_precio(ticker, key, mercado)
    llamadas = 1

    if cuerpo_precio.get("status") == "error" or "price" not in cuerpo_precio:
        raise RuntimeError(
            cuerpo_precio.get("message", f"No se pudo obtener el precio de {ticker}")
        )

    precio_divisa = float(cuerpo_precio["price"])

    if moneda_origen.upper() == "EUR":
        precio_eur = precio_divisa
    else:
        respuesta_cambio = httpx.get(
            f"{BASE_URL}/exchange_rate",
            params={"symbol": f"{moneda_origen.upper()}/EUR", "apikey": key},
            timeout=10,
        )
        llamadas += 1
        respuesta_cambio.raise_for_status()
        cuerpo_cambio = respuesta_cambio.json()

        if cuerpo_cambio.get("status") == "error" or "rate" not in cuerpo_cambio:
            raise RuntimeError(
                cuerpo_cambio.get(
                    "message", f"No se pudo obtener el cambio {moneda_origen}/EUR"
                )
            )

        precio_eur = precio_divisa * float(cuerpo_cambio["rate"])

    return {
        "cotizacion_divisa": precio_divisa,
        "cotizacion_eur": round(precio_eur, 4),
        "actualizada_en": datetime.now(timezone.utc),
        "llamadas": llamadas,
    }
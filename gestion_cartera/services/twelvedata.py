"""Cliente mínimo para la API de Twelve Data (https://twelvedata.com).

Solo dos funciones, que son las dos cosas que necesitamos:
- buscar_simbolo(texto): autocompletar al dar de alta un valor nuevo.
- obtener_cotizacion(ticker, moneda): refrescar el precio cacheado de un
  Valor (ver Valor.cotizacion_divisa / cotizacion_eur en models.py).

Requiere la variable de entorno TWELVEDATA_API_KEY. Consigue una clave
gratuita en https://twelvedata.com/pricing (plan "Basic", 800 peticiones/
día, 8/minuto). Configúrala como variable de entorno antes de arrancar
la app, por ejemplo en un archivo `.env` (no lo subas a git):

    TWELVEDATA_API_KEY=tu_clave_aqui

Este módulo se ejecuta siempre en el backend (nunca en el navegador del
usuario), así que la clave nunca queda expuesta en el cliente.
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
            "Consigue una clave gratis en https://twelvedata.com/pricing "
            "y expórtala antes de arrancar la app."
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


def obtener_cotizacion(ticker: str, moneda_origen: str) -> dict:
    """Devuelve el precio actual de `ticker` en su divisa original y su
    equivalente en euros.

    `moneda_origen` es la divisa del valor (p.ej. "USD"), tal como la
    devolvió buscar_simbolo() al darlo de alta — así evitamos tener que
    volver a preguntarle a la API qué divisa usa cada vez.

    Devuelve: {"cotizacion_divisa": float, "cotizacion_eur": float,
    "actualizada_en": datetime}. Si la moneda ya es EUR, no hace la
    segunda llamada de conversión (se ahorra una petición).
    """
    key = _api_key()

    respuesta_precio = httpx.get(
        f"{BASE_URL}/price",
        params={"symbol": ticker, "apikey": key},
        timeout=10,
    )
    respuesta_precio.raise_for_status()
    cuerpo_precio = respuesta_precio.json()

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
    }
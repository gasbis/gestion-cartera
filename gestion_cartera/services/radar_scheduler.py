"""Chequeo automático de RADAR en segundo plano (cierre del punto 5 del
encargo).

Hasta ahora, el aviso por SMS (ver radar_candidato_state.refrescar_cotizaciones)
solo se disparaba si alguien tenía la página /radar abierta -- al
cargarla, o al dar de alta un candidato nuevo. Si nadie la abría en
todo el día, la cotización se quedaba "congelada" con el último valor
visto y no se mandaba ningún SMS, aunque el precio real hubiera
cruzado el umbral.

Este módulo añade una tarea que vive dentro del propio proceso de la
app (arrancada en gestion_cartera.py vía `app.register_lifespan_task`,
ver https://reflex.dev/docs/utility-methods/lifespan-tasks/), sin
depender de que ningún usuario tenga el navegador abierto: cada hora
(ver `_proxima_ejecucion`), recorre TODOS los usuarios y las dos
listas (Largo Plazo y Corto Plazo), refresca la cotización de cada
valor en seguimiento UNA sola vez (Valor es una tabla compartida entre
usuarios, ver radar_db.obtener_valores_en_radar_global) y manda los
SMS que procedan, con la misma lógica de "ya avisado" que el refresco
manual.

Horario (hora de Madrid, de lunes a viernes -- ver
`_proxima_ejecucion`): de 9:20 a 22:20, una vez por hora. Se usa
Europe/Madrid (no una hora fija en UTC) para que el cambio de hora de
verano/invierno -- tanto el de España como el de EE.UU., que no
siempre cae el mismo día -- se ajuste solo, sin tener que tocar nada
dos veces al año.

El ancla en el minuto 20 (en vez de en punto) es a propósito: los
mercados europeos (BME, Euronext) sirven la cotización en Yahoo
Finance con ~15 min de retraso (ver
https://help.yahoo.com/kb/SLN2310.html), y aplicamos ese mismo margen
de prudencia a NASDAQ/NYSE aunque Yahoo los anuncie como "tiempo
real", porque en la práctica los datos que trae `yfinance` (misma vía
pública que un visitante anónimo de la web) no siempre lo son. Con el
ancla a los 20 minutos, el primer chequeo del día (9:20, veinte
minutos después de la apertura europea a las 9:00) ya refleja el
precio real de apertura, y cada consulta posterior tiene margen de
sobra sobre esos 15 min.

Protección ante más de una réplica de la app corriendo a la vez (varias
instancias en Railway mandarían cada una su propio SMS): antes de
hacer nada, cada pasada intenta "reservar" su hora programada en la
base de datos (ver radar_db.reclamar_ejecucion_horaria /
EjecucionRadarHoraria) -- si otro proceso ya se la reservó, esta
pasada no hace nada.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from gestion_cartera.auth_db import obtener_telefono_avisos
from gestion_cartera.cartera_db import guardar_cotizacion
from gestion_cartera.radar_db import (
    actualizar_alerta_enviada,
    actualizar_alerta_venta_enviada,
    obtener_candidatos,
    obtener_combinaciones_usuario_lista,
    obtener_valores_en_radar_global,
    reclamar_ejecucion_horaria,
)
from gestion_cartera.services import yahoo_finance
from gestion_cartera.services.twilio_sms import enviar_sms

ZONA_MADRID = ZoneInfo("Europe/Madrid")
HORA_INICIO = 9  # primer chequeo del día: HORA_INICIO:MINUTO_ANCLA
HORA_FIN = 22  # último chequeo del día: HORA_FIN:MINUTO_ANCLA
MINUTO_ANCLA = 20

# Igual que states/radar_candidato_state.PAUSA_ENTRE_COTIZACIONES: margen
# de prudencia entre peticiones a Yahoo Finance, no un límite documentado.
PAUSA_ENTRE_COTIZACIONES = 1


def _proxima_ejecucion(referencia: datetime) -> datetime:
    """Próximo instante (con tz, hora de Madrid) en el que toca chequeo
    automático: cada hora en punto + MINUTO_ANCLA minutos, entre
    HORA_INICIO y HORA_FIN, de lunes (0) a viernes (4)."""
    candidata = referencia.astimezone(ZONA_MADRID).replace(
        minute=MINUTO_ANCLA, second=0, microsecond=0
    )
    if candidata <= referencia.astimezone(ZONA_MADRID):
        candidata += timedelta(hours=1)
    while candidata.weekday() >= 5 or not (HORA_INICIO <= candidata.hour <= HORA_FIN):
        if candidata.weekday() >= 5 or candidata.hour > HORA_FIN:
            candidata = (candidata + timedelta(days=1)).replace(
                hour=HORA_INICIO, minute=MINUTO_ANCLA, second=0, microsecond=0
            )
        else:
            candidata = candidata.replace(
                hour=HORA_INICIO, minute=MINUTO_ANCLA, second=0, microsecond=0
            )
    return candidata


def _refrescar_todas_las_cotizaciones() -> None:
    """Pide a Yahoo Finance la cotización de cada valor distinto que
    aparece en cualquier lista de RADAR (de cualquier usuario) y la
    guarda. Bloqueante a propósito -- se llama desde un hilo aparte,
    ver `_ejecutar_chequeo_sync` / `tarea_radar_en_segundo_plano`."""
    valores = obtener_valores_en_radar_global()
    for i, v in enumerate(valores):
        try:
            cot = yahoo_finance.obtener_cotizacion(v["ticker"], v["moneda"], v["mercado"])
            guardar_cotizacion(
                v["id_valor"],
                cot["cotizacion_divisa"],
                cot["cotizacion_eur"],
                cot["actualizada_en"],
            )
        except Exception as e:
            print(
                f"[RADAR] (automático) Fallo al refrescar cotización de "
                f"{v['mercado']}:{v['ticker']}: {e}"
            )
        if i < len(valores) - 1:
            time.sleep(PAUSA_ENTRE_COTIZACIONES)


def _revisar_avisos_de_una_lista(id_usuario: int, tipo_lista: str) -> None:
    """Misma lógica de avisos de compra/venta que
    states/radar_candidato_state.refrescar_cotizaciones (ver ese
    método para los comentarios de detalle sobre el rearme de
    alerta_enviada/alerta_venta_enviada), pero para un (usuario,
    tipo_lista) concreto y llamada desde el chequeo automático."""
    telefono_avisos = obtener_telefono_avisos(id_usuario)
    candidatos = obtener_candidatos(id_usuario, tipo_lista)

    for candidato in candidatos:
        en_rojo = candidato["color_fila"] == "red"
        if en_rojo and not candidato["alerta_enviada"]:
            if telefono_avisos:
                try:
                    enviar_sms(
                        f"RADAR: {candidato['ticker']} ({candidato['empresa']}) ha "
                        f"alcanzado tu precio de compra "
                        f"({candidato['precio_max_mostrar']}). Cotización actual: "
                        f"{candidato['cotizacion_divisa_mostrar']}.",
                        telefono_avisos,
                    )
                    actualizar_alerta_enviada(candidato["id"], True)
                except Exception as e:
                    print(
                        f"[RADAR] (automático) Fallo al mandar aviso de compra por "
                        f"SMS de {candidato['ticker']}: {e}"
                    )
        elif not en_rojo and candidato["alerta_enviada"]:
            actualizar_alerta_enviada(candidato["id"], False)

        if candidato["alcanza_precio_venta"] and not candidato["alerta_venta_enviada"]:
            if telefono_avisos:
                try:
                    enviar_sms(
                        f"RADAR: {candidato['ticker']} ({candidato['empresa']}) ha "
                        f"alcanzado tu precio de venta "
                        f"({candidato['precio_min_mostrar']}). Cotización actual: "
                        f"{candidato['cotizacion_divisa_mostrar']}.",
                        telefono_avisos,
                    )
                    actualizar_alerta_venta_enviada(candidato["id"], True)
                except Exception as e:
                    print(
                        f"[RADAR] (automático) Fallo al mandar aviso de venta por "
                        f"SMS de {candidato['ticker']}: {e}"
                    )
        elif not candidato["alcanza_precio_venta"] and candidato["alerta_venta_enviada"]:
            actualizar_alerta_venta_enviada(candidato["id"], False)


def _ejecutar_chequeo_sync() -> None:
    """Todo el trabajo de un chequeo automático, de forma síncrona --
    se lanza en un hilo aparte (ver `tarea_radar_en_segundo_plano`)
    para no bloquear el resto de la app mientras dura, ya que puede
    tardar varios segundos si hay muchos valores distintos en
    seguimiento."""
    _refrescar_todas_las_cotizaciones()
    for id_usuario, tipo_lista in obtener_combinaciones_usuario_lista():
        try:
            _revisar_avisos_de_una_lista(id_usuario, tipo_lista)
        except Exception as e:
            print(
                f"[RADAR] (automático) Fallo revisando avisos de usuario "
                f"{id_usuario} / {tipo_lista}: {e}"
            )


async def tarea_radar_en_segundo_plano(app=None, starlette_app=None) -> None:
    """Tarea de fondo registrada en gestion_cartera.py vía
    `app.register_lifespan_task`: corre mientras viva el proceso de la
    app y, cada hora dentro del horario de mercado (ver
    `_proxima_ejecucion`), lanza un chequeo completo de RADAR para
    todos los usuarios."""
    print("[RADAR] Tarea de chequeo automático arrancada.")
    try:
        while True:
            proxima = _proxima_ejecucion(datetime.now(timezone.utc))
            espera = (proxima - datetime.now(ZONA_MADRID)).total_seconds()
            print(
                f"[RADAR] Próximo chequeo automático: "
                f"{proxima.strftime('%d/%m/%Y %H:%M')} (hora de Madrid)."
            )
            if espera > 0:
                await asyncio.sleep(espera)

            clave = proxima.strftime("%Y-%m-%dT%H:%M")
            if not await asyncio.to_thread(reclamar_ejecucion_horaria, clave):
                print(
                    f"[RADAR] El chequeo de las {clave} ya lo ha hecho otro "
                    f"proceso -- se salta."
                )
                continue

            print(f"[RADAR] Chequeo automático de las {clave} (hora de Madrid) -- empieza.")
            try:
                await asyncio.to_thread(_ejecutar_chequeo_sync)
            except Exception as e:
                print(f"[RADAR] (automático) Fallo inesperado en el chequeo de las {clave}: {e}")
            print(f"[RADAR] Chequeo automático de las {clave} -- terminado.")
    except asyncio.CancelledError:
        print("[RADAR] Tarea de chequeo automático detenida (apagado de la app).")
        raise

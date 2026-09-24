"""Cliente mínimo para mandar avisos por WhatsApp vía la API de Twilio
(https://www.twilio.com/docs/whatsapp/api), para el sistema de alertas
de RADAR (punto 5 del encargo) cuando la cotización de un candidato
alcanza su precio de compra o de venta.

Fase actual: cuenta Twilio Trial + sandbox de WhatsApp. El sandbox
SOLO puede mandar mensajes a un número que se haya unido a él (mandando
"join <palabra-clave>" al número de sandbox desde ese WhatsApp), y ese
vínculo caduca a las 72h de inactividad -- cada usuario tiene que
volver a unirse de vez en cuando mientras sigamos en Trial. El sandbox
sí admite varios números distintos a la vez (cada uno debe unirse por
su cuenta), así que el destinatario ya se lee por usuario (ver
Usuario.telefono_whatsapp en models.py) en vez de un único número fijo.
Cuando haya un WhatsApp Sender de producción aprobado, este mismo
`enviar_whatsapp` seguirá funcionando igual -- solo deja de hacer falta
el paso de "join" para cada usuario.

Variables de entorno necesarias (en `.env`, nunca en el código):
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_WHATSAPP_FROM   (el número de sandbox, con o sin prefijo "whatsapp:")
"""

import os

import httpx

BASE_URL = "https://api.twilio.com/2010-04-01"


def _config() -> tuple[str, str, str]:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    numero_origen = os.environ.get("TWILIO_WHATSAPP_FROM")
    faltan = [
        nombre
        for nombre, valor in [
            ("TWILIO_ACCOUNT_SID", account_sid),
            ("TWILIO_AUTH_TOKEN", auth_token),
            ("TWILIO_WHATSAPP_FROM", numero_origen),
        ]
        if not valor
    ]
    if faltan:
        raise RuntimeError(
            "Faltan variables de entorno para Twilio: " + ", ".join(faltan)
        )
    return account_sid, auth_token, numero_origen


def _con_prefijo_whatsapp(numero: str) -> str:
    return numero if numero.startswith("whatsapp:") else f"whatsapp:{numero}"


def enviar_whatsapp(mensaje: str, numero_destino: str) -> None:
    """Manda `mensaje` por WhatsApp a `numero_destino` (formato
    internacional, p.ej. "+34600000000" -- ver
    Usuario.telefono_whatsapp). Lanza una excepción (con el detalle que
    devuelva Twilio) si el envío falla -- quien la llame decide si eso
    debe cortar el resto del proceso o solo registrarse como aviso
    fallido."""
    account_sid, auth_token, numero_origen = _config()
    respuesta = httpx.post(
        f"{BASE_URL}/Accounts/{account_sid}/Messages.json",
        auth=(account_sid, auth_token),
        data={
            "From": _con_prefijo_whatsapp(numero_origen),
            "To": _con_prefijo_whatsapp(numero_destino),
            "Body": mensaje,
        },
        timeout=10,
    )
    try:
        respuesta.raise_for_status()
    except httpx.HTTPStatusError as e:
        # httpx no incluye el cuerpo de la respuesta en el mensaje de
        # la excepción -- Twilio siempre manda un JSON con "message" y
        # "code" explicando el motivo (nº no unido al sandbox, formato
        # de número inválido, etc.), así que lo añadimos aquí para no
        # tener que ir a mirar los logs de Twilio a cada fallo.
        raise RuntimeError(f"Twilio respondió {respuesta.status_code}: {respuesta.text}") from e

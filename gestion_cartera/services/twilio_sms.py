"""Cliente mínimo para mandar avisos por SMS vía la API de Twilio, para
el sistema de alertas de RADAR (punto 5 del encargo) cuando la
cotización de un candidato alcanza su precio de compra o de venta.

Reemplaza a services/twilio_whatsapp.py (que se deja sin usar, no se
borra por si se retoma WhatsApp en el futuro): el WhatsApp Sender de
producción de Meta exige verificar una empresa real (CIF/escritura,
etc.), y este es un proyecto personal sin actividad registrada, así que
no era viable -- el SMS de Twilio no tiene ese requisito.

A diferencia del WhatsApp Sandbox, el SMS:
- No caduca (nada de "join <palabra-clave>" cada 72h).
- No necesita ninguna plantilla aprobada por Meta -- se manda texto
  libre igual que en el sandbox de WhatsApp.
- Tiene un coste por mensaje (unos céntimos, según el país de destino).

Variables de entorno necesarias (en `.env`, nunca en el código):
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_SMS_FROM   (el número de Twilio comprado para esto, formato
  internacional, p.ej. "+16105461454" -- SIN prefijo "whatsapp:")
"""

import os

import httpx

BASE_URL = "https://api.twilio.com/2010-04-01"


def _config() -> tuple[str, str, str]:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    numero_origen = os.environ.get("TWILIO_SMS_FROM")
    faltan = [
        nombre
        for nombre, valor in [
            ("TWILIO_ACCOUNT_SID", account_sid),
            ("TWILIO_AUTH_TOKEN", auth_token),
            ("TWILIO_SMS_FROM", numero_origen),
        ]
        if not valor
    ]
    if faltan:
        raise RuntimeError(
            "Faltan variables de entorno para Twilio: " + ", ".join(faltan)
        )
    return account_sid, auth_token, numero_origen


def enviar_sms(mensaje: str, numero_destino: str) -> None:
    """Manda `mensaje` por SMS a `numero_destino` (formato
    internacional, p.ej. "+34600000000" -- ver
    Usuario.telefono_avisos). Lanza una excepción (con el detalle que
    devuelva Twilio) si el envío falla -- quien la llame decide si eso
    debe cortar el resto del proceso o solo registrarse como aviso
    fallido."""
    account_sid, auth_token, numero_origen = _config()
    respuesta = httpx.post(
        f"{BASE_URL}/Accounts/{account_sid}/Messages.json",
        auth=(account_sid, auth_token),
        data={
            "From": numero_origen,
            "To": numero_destino,
            "Body": mensaje,
        },
        timeout=10,
    )
    try:
        respuesta.raise_for_status()
    except httpx.HTTPStatusError as e:
        # httpx no incluye el cuerpo de la respuesta en el mensaje de
        # la excepción -- Twilio siempre manda un JSON con "message" y
        # "code" explicando el motivo, así que lo añadimos aquí para no
        # tener que ir a mirar los logs de Twilio a cada fallo.
        raise RuntimeError(f"Twilio respondió {respuesta.status_code}: {respuesta.text}") from e

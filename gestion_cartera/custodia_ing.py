"""Aviso por SMS de la comisión de custodia de ING.

ING no cobra la comisión de custodia si en cada trimestre natural se
hace al menos una compra o una venta. Este módulo avisa por SMS, a
partir de `DIAS_ANTES_FIN` días antes de que acabe el trimestre, a cada
usuario que:
  - tiene algún valor depositado en ING (en cualquiera de sus dos
    carteras -- la condición es por usuario, no por cartera, igual que
    en el extracto del bróker; ver cartera_db.obtener_existencias_broker), y
  - todavía no ha registrado ninguna Compra ni Venta en ING dentro del
    trimestre en curso (en ninguna de sus dos carteras).

Se comprueba en cada pasada del chequeo automático en segundo plano
(services/radar_scheduler.py: de lunes a viernes, cada hora de 9:20 a
22:20, hora de Madrid), así que el SMS sale en la primera pasada a partir
del día de aviso -- si ese día cae en fin de semana, el lunes siguiente.
Se manda COMO MUCHO UNA VEZ por usuario y trimestre: si después de
avisar se sigue sin operar, no se repite.

Para no mandarlo dos veces (varias réplicas de la app, o varias pasadas
en el mismo día) se reutiliza el mismo "cerrojo" en base de datos que el
chequeo de RADAR (models.EjecucionRadarHoraria, clave única): la clave
de este aviso es "custodia-ING:<año>T<trimestre>:u<id_usuario>", p.ej.
"custodia-ING:2026T4:u3". Si el envío del SMS falla, se borra la clave
para que se vuelva a intentar en la pasada siguiente.
"""

from datetime import date, timedelta

import reflex as rx
import sqlmodel

from gestion_cartera.cartera_db import obtener_existencias_broker
from gestion_cartera.models import Cartera, EjecucionRadarHoraria, Operacion, Usuario
from gestion_cartera.operaciones_db import obtener_broker_id_por_nombre
from gestion_cartera.radar_db import reclamar_ejecucion_horaria
from gestion_cartera.services.twilio_sms import enviar_sms

NOMBRE_BROKER = "ING"
DIAS_ANTES_FIN = 15


def trimestre(fecha: date) -> tuple[int, date, date]:
    """(nº de trimestre 1-4, primer día, último día) del trimestre
    natural al que pertenece `fecha`."""
    n = (fecha.month - 1) // 3 + 1
    inicio = date(fecha.year, 3 * n - 2, 1)
    siguiente = date(fecha.year + 1, 1, 1) if n == 4 else date(fecha.year, 3 * n + 1, 1)
    return n, inicio, siguiente - timedelta(days=1)


def _ha_operado_en_trimestre(id_usuario: int, id_broker: int, inicio: date, fin: date) -> bool:
    """¿Alguna Compra o Venta en este bróker, en cualquiera de las
    carteras del usuario, con fecha dentro del trimestre?"""
    with rx.session() as session:
        op = session.exec(
            sqlmodel.select(Operacion.id)
            .join(Cartera, Cartera.id == Operacion.id_cartera)
            .where(
                Cartera.id_usuario == id_usuario,
                Operacion.id_broker == id_broker,
                Operacion.tipo_operacion.in_(("Compra", "Venta")),
                Operacion.fecha >= inicio,
                Operacion.fecha <= fin,
            )
        ).first()
        return op is not None


def _liberar_clave(clave: str) -> None:
    with rx.session() as session:
        fila = session.exec(
            sqlmodel.select(EjecucionRadarHoraria).where(EjecucionRadarHoraria.clave == clave)
        ).first()
        if fila is not None:
            session.delete(fila)
            session.commit()


def usuarios_a_avisar(hoy: date) -> list[dict]:
    """Usuarios activos, con teléfono de avisos, valores en ING y sin
    ninguna Compra/Venta en ING este trimestre -- solo a partir del día
    de aviso del trimestre (si no, lista vacía). No manda nada: separado
    de `revisar_avisos_custodia` para poder comprobarlo sin enviar SMS."""
    n, inicio, fin = trimestre(hoy)
    if hoy < fin - timedelta(days=DIAS_ANTES_FIN):
        return []
    id_broker = obtener_broker_id_por_nombre(NOMBRE_BROKER)
    if id_broker is None:
        return []

    with rx.session() as session:
        usuarios = session.exec(
            sqlmodel.select(Usuario).where(Usuario.activo == True)  # noqa: E712
        ).all()
        usuarios = [(u.id, u.nombre, u.telefono_avisos) for u in usuarios]

    resultado = []
    for id_usuario, nombre, telefono in usuarios:
        if not telefono:
            continue
        if not obtener_existencias_broker(id_broker, id_usuario):
            continue
        if _ha_operado_en_trimestre(id_usuario, id_broker, inicio, fin):
            continue
        resultado.append(
            {
                "id_usuario": id_usuario,
                "nombre": nombre,
                "telefono": telefono,
                "clave": f"custodia-{NOMBRE_BROKER}:{hoy.year}T{n}:u{id_usuario}",
                "mensaje": (
                    f"GestiOn Cartera: sin compras ni ventas en {NOMBRE_BROKER} este "
                    f"trimestre ({n}T {hoy.year}). Para evitar la comisiOn de custodia, "
                    f"opera antes del {fin.strftime('%d/%m/%Y')}."
                ),
            }
        )
    return resultado


def revisar_avisos_custodia(hoy: date) -> None:
    """Manda el SMS a cada usuario de `usuarios_a_avisar` que aún no lo
    haya recibido este trimestre. Bloqueante: se llama desde el hilo del
    chequeo automático (services/radar_scheduler._ejecutar_chequeo_sync)."""
    for aviso in usuarios_a_avisar(hoy):
        if not reclamar_ejecucion_horaria(aviso["clave"]):
            continue  # ya avisado este trimestre
        try:
            enviar_sms(aviso["mensaje"], aviso["telefono"])
            print(f"[CUSTODIA] Aviso enviado a {aviso['nombre']} ({aviso['clave']}).")
        except Exception as e:
            _liberar_clave(aviso["clave"])
            print(f"[CUSTODIA] Fallo al mandar el aviso a {aviso['nombre']}: {e}")

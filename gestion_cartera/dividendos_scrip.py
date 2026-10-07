"""Valoración de los dividendos cobrados "en acciones" (Script) y su
presentación junto a los dividendos en efectivo.

Un Script (dividendo flexible / scrip dividend) puede pagarse de tres
formas, y la app ya registra el dinero que se mueve en cada una:
  - Venta de derechos: el dinero cobrado (`importe`) ya cuenta como
    dividendo en toda la app.
  - Compra de derechos: se pagó `importe` para completar títulos
    nuevos -- es un coste, no un ingreso.
  - Sin dinero de por medio: solo se reciben títulos.
Lo que NO se registraba es lo que valían los títulos nuevos recibidos.
Eso es `Operacion.valoracion_script_eur` (cotización de cierre de ese
día x títulos recibidos, en euros), y aquí se convierte en el "valor
neto del scrip" que se suma a los dividendos:

    valor neto = valoración de los títulos
                 - lo pagado por comprar derechos (si se compraron)

En la venta de derechos el dinero cobrado ya está sumado como dividendo,
así que solo se añade la valoración de los títulos.

Criterio de presentación (petición del usuario, 07/10/2026): en todos
los informes que muestran dividendos, la cifra de siempre (solo
efectivo) y, ENTRE PARÉNTESIS, la cifra incluyendo la valoración de los
scrips -- p.ej. "1.234,56 € (1.456,78 €)". Si en ese dato no hay ningún
scrip valorado, se muestra la cifra sola, sin paréntesis. La página
IRPF NO lo aplica a propósito: los títulos recibidos en un scrip no
tributan hasta que se venden, así que sumarlos ahí confundiría la
declaración.
"""

import logging
from collections.abc import Callable

import reflex as rx

from gestion_cartera.models import Operacion, Valor

log = logging.getLogger(__name__)

# Por debajo de esto (en euros o en puntos porcentuales) dos cifras se
# consideran iguales y no se añade el paréntesis.
_TOLERANCIA = 0.005


def valor_neto_scrip(op: Operacion) -> float:
    """Euros que hay que SUMAR a los dividendos en efectivo por este
    Script (0.0 para cualquier otra operación, o si el Script aún no
    está valorado)."""
    if op.tipo_operacion != "Script" or op.valoracion_script_eur is None:
        return 0.0
    pagado = (op.importe or 0.0) if op.tipo_derecho_script == "Compra" else 0.0
    return max(op.valoracion_script_eur - pagado, 0.0)


def es_dividendo_efectivo(op: Operacion) -> bool:
    """Lo que la app siempre ha contado como dividendo: Dividendo, y
    Script con derecho VENDIDO (el dinero cobrado por los derechos)."""
    return op.tipo_operacion == "Dividendo" or (
        op.tipo_operacion == "Script" and op.tipo_derecho_script == "Venta"
    )


def mostrar_con_scrip(
    sin_scrip: float, con_scrip: float, formatear: Callable[[float], str]
) -> str:
    """'X' si no hay diferencia; 'X (Y)' si la valoración de los scrips
    cambia la cifra."""
    if abs(con_scrip - sin_scrip) < _TOLERANCIA:
        return formatear(sin_scrip)
    return f"{formatear(sin_scrip)} ({formatear(con_scrip)})"


def valorar_script(id_operacion: int) -> float | None:
    """Calcula y guarda `valoracion_script_eur` de un Script (cotización
    de cierre del día de la operación x títulos recibidos, en euros).
    Se llama al dar de alta y al editar un Script; si Yahoo Finance no
    devuelve precio, la valoración queda en None (sin valorar) y la
    operación se guarda igualmente -- nunca bloquea el alta."""
    from gestion_cartera.services.yahoo_finance import obtener_cierre_eur

    with rx.session() as session:
        op = session.get(Operacion, id_operacion)
        if op is None or op.tipo_operacion != "Script":
            return None
        valor = session.get(Valor, op.id_valor)
        if valor is None:
            return None
        try:
            precio = obtener_cierre_eur(valor.ticker, valor.moneda, valor.mercado, op.fecha)
        except Exception as e:  # red, símbolo no encontrado, etc.
            log.warning("No se pudo valorar el Script %s (%s): %s", id_operacion, valor.ticker, e)
            precio = None
        op.valoracion_script_eur = (
            round(precio * op.num_titulos, 2) if precio is not None else None
        )
        session.add(op)
        session.commit()
        return op.valoracion_script_eur


def scripts_sin_valorar(desde=None) -> list[int]:
    """Ids de los Script sin `valoracion_script_eur` (con fecha a partir
    de `desde`, si se indica)."""
    import sqlmodel

    with rx.session() as session:
        consulta = sqlmodel.select(Operacion.id).where(
            Operacion.tipo_operacion == "Script", Operacion.valoracion_script_eur.is_(None)
        )
        if desde is not None:
            consulta = consulta.where(Operacion.fecha >= desde)
        return list(session.exec(consulta).all())


def valorar_scripts_pendientes(desde=None) -> dict:
    """Valora (ver `valorar_script`) todos los Script que siguen sin
    valoración. Lo llaman el chequeo automático diario (solo los de los
    últimos meses: los que no se pudieron valorar al darlos de alta) y
    preparar_historicos.py (todos). Devuelve {"valorados", "sin_precio"}."""
    resumen = {"valorados": 0, "sin_precio": 0}
    for id_operacion in scripts_sin_valorar(desde):
        if valorar_script(id_operacion) is None:
            resumen["sin_precio"] += 1
        else:
            resumen["valorados"] += 1
    return resumen

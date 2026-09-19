"""Siembra idempotente de la tabla BROKERS con los brokers iniciales.

Ejecutar con: uv run python -m gestion_cartera.seed_brokers
"""

import reflex as rx
import sqlmodel

from gestion_cartera.models import Broker

BROKERS_INICIALES = ["ING", "Trade Republic", "Interactive Brokers"]


def seed_brokers() -> int:
    """Inserta los brokers iniciales que aún no existan. Devuelve cuántos
    se han insertado (0 si ya estaban todos)."""
    insertados = 0
    with rx.session() as session:
        existentes = {b.nombre for b in session.exec(sqlmodel.select(Broker)).all()}
        for nombre in BROKERS_INICIALES:
            if nombre in existentes:
                continue
            session.add(Broker(nombre=nombre))
            insertados += 1
        session.commit()
    return insertados


if __name__ == "__main__":
    n = seed_brokers()
    print(f"Brokers insertados: {n}")

"""Rellena `importe` en las filas de MATRIZ de Spinoff antiguas (importe 0).

Desde el 28/09/2026 la fila de la matriz guarda el coste que traspasa a
la filial (el mismo importe que su fila de filial enlazada) y el motor
FIFO lo resta de sus lotes en proporción al coste de cada uno. Las filas
antiguas solo tenían el %, que aplicado una vez por bróker daba un coste
incorrecto si la matriz estaba en varios brókers.

Uso (desde la carpeta del proyecto):
    uv run python migrar_spinoff_importe_matriz.py            # Railway, solo muestra
    uv run python migrar_spinoff_importe_matriz.py --aplicar  # Railway, guarda
    uv run python migrar_spinoff_importe_matriz.py --local [--aplicar]   # reflex.db

Railway: toma la URL de la línea `# DATABASE_URL=...` del .env (aunque
esté comentada), salvo que ya exista la variable de entorno.
"""

import os
import re
import sys
from pathlib import Path

APLICAR = "--aplicar" in sys.argv
LOCAL = "--local" in sys.argv

if LOCAL:
    os.environ.pop("DATABASE_URL", None)
elif not os.environ.get("DATABASE_URL"):
    for linea in Path(".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*#?\s*DATABASE_URL\s*=\s*(\S+)", linea)
        if m:
            os.environ["DATABASE_URL"] = m.group(1)
            break
    if not os.environ.get("DATABASE_URL"):
        sys.exit("No encuentro DATABASE_URL en .env (usa --local para reflex.db)")

import sqlmodel  # noqa: E402
import reflex as rx  # noqa: E402

from gestion_cartera.models import Operacion, Valor  # noqa: E402

print("Base de datos:", "LOCAL (reflex.db)" if LOCAL else "RAILWAY")
print("Modo:", "APLICAR (se guardan cambios)" if APLICAR else "SOLO MOSTRAR (no se guarda nada)")
print()

with rx.session() as s:
    matrices = s.exec(
        sqlmodel.select(Operacion).where(
            Operacion.tipo_operacion == "Spinoff",
            Operacion.num_titulos == 0,
        )
    ).all()

    cambios = 0
    for m in matrices:
        if m.importe and m.importe > 0:
            continue
        filial = s.exec(
            sqlmodel.select(Operacion).where(
                Operacion.id_cartera == m.id_cartera,
                Operacion.id_broker == m.id_broker,
                Operacion.fecha == m.fecha,
                Operacion.tipo_operacion == "Spinoff",
                Operacion.num_titulos > 0,
                Operacion.id_valor == m.id_valor_relacionado,
            )
        ).first()
        vm = s.get(Valor, m.id_valor)
        vf = s.get(Valor, m.id_valor_relacionado) if m.id_valor_relacionado else None
        etiqueta = (
            f"op {m.id}  cartera {m.id_cartera}  {m.fecha}  "
            f"{vm.ticker if vm else m.id_valor} -> {vf.ticker if vf else '?'}"
        )
        if filial is None:
            print(f"SIN FILIAL ENLAZADA, revisar a mano: {etiqueta}")
            continue
        print(f"{etiqueta}  importe 0 -> {filial.importe:.2f}")
        cambios += 1
        if APLICAR:
            m.importe = filial.importe
            s.add(m)
    if APLICAR:
        s.commit()

print(f"\n{cambios} fila(s) {'actualizadas' if APLICAR else 'a actualizar'}.")
if cambios and not APLICAR:
    print("Vuelve a ejecutar con --aplicar para guardar.")

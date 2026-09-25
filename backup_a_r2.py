# -*- coding: utf-8 -*-
"""Backup mensual de la base de datos de producción (Postgres en Railway)
a un bucket de Cloudflare R2 -- pensado para ejecutarse como un
servicio "Cron Job" aparte en Railway (mismo repo, arrancando este
script en vez de la app web; ver la conversación de configuración para
los pasos exactos de Cloudflare/Railway).

Sin cifrar a propósito: no hay datos personales que proteger, solo
valores/operaciones de cartera, así que no compensa la complejidad
añadida de gestionar una clave de cifrado aparte.

Formato: SQL plano comprimido con gzip (no el formato "custom" de
pg_dump) para que el volcado se pueda restaurar en cualquier Postgres,
sin depender de que la versión de `pg_restore` coincida con la que lo
generó -- basta con `gunzip -c backup.sql.gz | psql <DATABASE_URL>`.
Se sube como `backups/gestion-cartera-AAAA-MM.sql.gz`: si el cron se
volviera a disparar el mismo mes, sobrescribe el mismo objeto en vez
de acumular copias duplicadas.

Variables de entorno necesarias (se configuran en la pestaña
"Variables" del servicio de backup en Railway -- nunca en este
archivo ni en el repositorio):
    DATABASE_URL          Misma cadena de conexión de Postgres que usa
                           la app web -- mejor referenciada desde la
                           variable del servicio de Postgres que
                           copiada a mano, para que si cambia algún día
                           no haya que tocar esto también.
    R2_ACCOUNT_ID          ID de cuenta de Cloudflare (compone el
                           endpoint S3 de R2).
    R2_ACCESS_KEY_ID       Del token de API de R2.
    R2_SECRET_ACCESS_KEY   Del token de API de R2.
    R2_BUCKET              Nombre del bucket de R2 donde se sube.

Necesita el binario `pg_dump` disponible en el entorno de ejecución
(ver nixpacks.toml, aptPkgs) y el paquete `boto3` instalado (ver
pyproject.toml).
"""

import gzip
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone

import boto3

NOMBRE_APP = "gestion-cartera"


def _database_url_para_pg_dump() -> str:
    """`pg_dump` no entiende el prefijo `postgresql+psycopg://` que usa
    rxconfig.py para indicarle el driver a SQLAlchemy -- necesita la
    URL "normal" de Postgres (`postgresql://...`)."""
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


def _volcar_base_de_datos(ruta_sql: str) -> None:
    """SQL plano, sin propietario ni permisos (--no-owner --no-acl):
    así el volcado se puede restaurar en una base Postgres nueva sin
    arrastrar roles que no vayan a existir allí."""
    url = _database_url_para_pg_dump()
    resultado = subprocess.run(
        ["pg_dump", "--no-owner", "--no-acl", "-f", ruta_sql, url],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"pg_dump ha fallado: {resultado.stderr.strip()}")


def _comprimir(ruta_sql: str, ruta_gz: str) -> None:
    with open(ruta_sql, "rb") as origen, gzip.open(ruta_gz, "wb") as destino:
        destino.writelines(origen)


def _subir_a_r2(ruta_gz: str, nombre_objeto: str) -> None:
    cliente = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    cliente.upload_file(ruta_gz, os.environ["R2_BUCKET"], nombre_objeto)


def main() -> None:
    hoy = date.today()
    nombre_objeto = f"backups/{NOMBRE_APP}-{hoy.strftime('%Y-%m')}.sql.gz"

    with tempfile.TemporaryDirectory() as tmp:
        ruta_sql = os.path.join(tmp, "backup.sql")
        ruta_gz = os.path.join(tmp, "backup.sql.gz")

        print("[BACKUP] Volcando base de datos...", flush=True)
        _volcar_base_de_datos(ruta_sql)

        print("[BACKUP] Comprimiendo...", flush=True)
        _comprimir(ruta_sql, ruta_gz)

        tamano_mb = os.path.getsize(ruta_gz) / (1024 * 1024)
        print(
            f"[BACKUP] Subiendo a R2 como «{nombre_objeto}» ({tamano_mb:.2f} MB)...",
            flush=True,
        )
        _subir_a_r2(ruta_gz, nombre_objeto)

    print(f"[BACKUP] Completado: {datetime.now(timezone.utc).isoformat()}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[BACKUP] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

"""Renombra grupos de industria mal traducidos o poco claros en SECTORES

Corrige la traducción de algunos de los 55 grupos Morningstar para que
se vea qué contienen (p. ej. "Utilities - Regulated" incluye gas y agua,
no solo eléctricas; "Consumer Packaged Goods" incluye la alimentación).
Solo cambia el texto de `grupo`: los ids no cambian, así que los
valores ya clasificados (valores.id_sector) siguen apuntando a la misma
fila. seed_sectores.py ya usa los nombres nuevos, de modo que volver a
ejecutarlo después de esta migración no duplica filas.

Revision ID: d5a8f3c1e7b2
Revises: b7d1e4a9c2f3
Create Date: 2026-10-09 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5a8f3c1e7b2'
down_revision: Union[str, Sequence[str], None] = 'b7d1e4a9c2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (sector, grupo antiguo, grupo nuevo)
_RENOMBRADOS = [
    ("Consumo Defensivo", "Bienes de Consumo Envasados",
     "Alimentación, Higiene y Hogar (envasados)"),
    ("Consumo Defensivo", "Distribución - Defensiva",
     "Distribución - Defensiva (supermercados)"),
    ("Servicios Públicos", "Eléctricas Reguladas",
     "Servicios Públicos Regulados (electricidad, gas, agua)"),
    ("Servicios Públicos", "Eléctricas - Productores Independientes",
     "Productores Independientes y Renovables"),
    ("Consumo Cíclico", "Fabricación - Textil y Mobiliario",
     "Fabricación - Textil y Complementos"),
]

_SQL = sa.text(
    "UPDATE sectores SET grupo = :nuevo WHERE sector = :sector AND grupo = :antiguo"
)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    for sector, antiguo, nuevo in _RENOMBRADOS:
        conn.execute(_SQL, {"sector": sector, "antiguo": antiguo, "nuevo": nuevo})


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for sector, antiguo, nuevo in _RENOMBRADOS:
        conn.execute(_SQL, {"sector": sector, "antiguo": nuevo, "nuevo": antiguo})

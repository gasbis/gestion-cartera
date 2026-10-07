"""valoracion_script_eur en operaciones y tabla cierres_diarios

Revision ID: b7d1e4a9c2f3
Revises: 74a2399fa7e7
Create Date: 2026-10-07 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7d1e4a9c2f3'
down_revision: Union[str, Sequence[str], None] = '74a2399fa7e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('operaciones', schema=None) as batch_op:
        batch_op.add_column(sa.Column('valoracion_script_eur', sa.Float(), nullable=True))

    op.create_table(
        'cierres_diarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_valor', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('cierre_eur', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['id_valor'], ['valores.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id_valor', 'fecha', name='uq_cierre_valor_fecha'),
    )
    with op.batch_alter_table('cierres_diarios', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_cierres_diarios_id_valor'), ['id_valor'], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('cierres_diarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cierres_diarios_id_valor'))
    op.drop_table('cierres_diarios')

    with op.batch_alter_table('operaciones', schema=None) as batch_op:
        batch_op.drop_column('valoracion_script_eur')

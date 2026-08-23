"""add embedding_error to papers

Revision ID: c7a5e2b18f33
Revises: b3f21d9c7e40
Create Date: 2026-08-22 11:03:27.559812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a5e2b18f33'
down_revision: Union[str, Sequence[str], None] = 'b3f21d9c7e40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: papers that never failed have nothing to record.
    op.add_column('papers', sa.Column('embedding_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('papers', 'embedding_error')

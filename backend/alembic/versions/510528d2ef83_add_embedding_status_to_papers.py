"""add embedding_status to papers

Revision ID: 510528d2ef83
Revises: 1f461ef16460
Create Date: 2026-08-20 10:12:44.318902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '510528d2ef83'
down_revision: Union[str, Sequence[str], None] = '1f461ef16460'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default is what lets a NOT NULL column land on a table that
    # already has rows, without a separate backfill.
    op.add_column(
        'papers',
        sa.Column(
            'embedding_status',
            sa.String(length=20),
            server_default='not_embedded',
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('papers', 'embedding_status')

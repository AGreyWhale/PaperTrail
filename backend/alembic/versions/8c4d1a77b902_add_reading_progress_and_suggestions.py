"""add reading progress and cached suggestions to papers

Revision ID: 8c4d1a77b902
Revises: 510528d2ef83
Create Date: 2026-08-21 13:42:08.114003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c4d1a77b902'
down_revision: Union[str, Sequence[str], None] = '510528d2ef83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # All nullable: existing papers simply haven't been opened yet.
    op.add_column('papers', sa.Column('last_opened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('papers', sa.Column('last_page', sa.Integer(), nullable=True))
    op.add_column('papers', sa.Column('suggested_questions', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('papers', 'suggested_questions')
    op.drop_column('papers', 'last_page')
    op.drop_column('papers', 'last_opened_at')

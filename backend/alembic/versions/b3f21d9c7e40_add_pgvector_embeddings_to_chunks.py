"""add pgvector embeddings to chunks

Revision ID: b3f21d9c7e40
Revises: e8b4368769d7
Create Date: 2026-08-22 09:14:52.771204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'b3f21d9c7e40'
down_revision: Union[str, Sequence[str], None] = 'e8b4368769d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Must come before the column: the type doesn't exist until the extension does.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Nullable — existing chunks have no embedding yet and are re-embedded on
    # demand, so there's nothing sensible to backfill.
    op.add_column('chunks', sa.Column('embedding', Vector(384), nullable=True))

    # Vectors previously lived in Chroma, which this migration retires. Any
    # paper already marked "embedded" now has no vectors at all, so search
    # would silently return nothing while the UI claimed it was ready. Reset
    # them so the app asks for a re-embed instead of lying.
    op.execute(
        "UPDATE papers SET embedding_status = 'not_embedded' "
        "WHERE embedding_status = 'embedded'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chunks', 'embedding')
    # The extension is left in place: other objects may depend on it, and
    # dropping it is not reversible in a useful way.

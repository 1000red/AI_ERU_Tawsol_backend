"""add blacklisted_tokens

Revision ID: 42adec70d4a4
Revises: ccbf97eebf02
Create Date: 2026-05-23 01:10:31.931065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42adec70d4a4'
down_revision: Union[str, None] = 'ccbf97eebf02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # blacklisted_tokens was already created by create_all on first run
    pass


def downgrade() -> None:
    op.drop_table('blacklisted_tokens')

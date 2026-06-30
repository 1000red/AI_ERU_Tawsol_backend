"""add_current_password_to_users

Revision ID: 4715e77cb68d
Revises: 42adec70d4a4
Create Date: 2026-05-24 19:49:02.699890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4715e77cb68d'
down_revision: Union[str, None] = '42adec70d4a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('current_password', sa.Boolean(), nullable=False, server_default='true'),
    )


def downgrade() -> None:
    op.drop_column('users', 'current_password')

"""remove profile_picture from users

Revision ID: f3a1d9e82c05
Revises: 01e136d5ae51
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a1d9e82c05'
down_revision: Union[str, None] = '01e136d5ae51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('users', 'profile_picture')


def downgrade() -> None:
    op.add_column('users', sa.Column('profile_picture', sa.String(length=255), nullable=True))

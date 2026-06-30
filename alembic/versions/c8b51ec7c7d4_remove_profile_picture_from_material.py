"""remove profile_picture from material

Revision ID: c8b51ec7c7d4
Revises: bb7cabb91da8
Create Date: 2026-05-24 23:02:21.031660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b51ec7c7d4'
down_revision: Union[str, None] = 'bb7cabb91da8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('material', 'profile_picture')


def downgrade() -> None:
    op.add_column('material', sa.Column('profile_picture', sa.VARCHAR(length=255), autoincrement=False, nullable=True))

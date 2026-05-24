"""rename_must_change_password_to_current_password

Revision ID: bb7cabb91da8
Revises: 4715e77cb68d
Create Date: 2026-05-24 19:55:13.040981

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb7cabb91da8'
down_revision: Union[str, None] = '4715e77cb68d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'must_change_password', new_column_name='current_password')


def downgrade() -> None:
    op.alter_column('users', 'current_password', new_column_name='must_change_password')

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
    # Repair: this revision was written to rename must_change_password ->
    # current_password, but by the time the chain reaches it, must_change_password
    # has already been dropped (ccbf97eebf02) and current_password has already been
    # added (4715e77cb68d), so the unguarded rename fails on every path
    # ("column must_change_password does not exist" / duplicate current_password).
    # Apply the rename only when it is actually meaningful; otherwise this
    # revision is already in its intended end state.
    conn = op.get_bind()
    src = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'must_change_password'"
    )).fetchone()
    dst = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'current_password'"
    )).fetchone()
    if src and not dst:
        op.alter_column('users', 'must_change_password', new_column_name='current_password')


def downgrade() -> None:
    op.alter_column('users', 'current_password', new_column_name='must_change_password')

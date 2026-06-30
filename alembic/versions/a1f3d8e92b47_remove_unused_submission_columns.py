"""remove unused submission columns (title, description, text_content)

Revision ID: a1f3d8e92b47
Revises: c8b51ec7c7d4
Create Date: 2026-06-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f3d8e92b47'
down_revision: Union[str, None] = '9f5290e53baa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('assignment_submissions', 'title')
    op.drop_column('assignment_submissions', 'description')
    op.drop_column('assignment_submissions', 'text_content')


def downgrade() -> None:
    op.add_column('assignment_submissions', sa.Column('text_content', sa.Text(), nullable=True))
    op.add_column('assignment_submissions', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('assignment_submissions', sa.Column('title', sa.String(200), nullable=True))

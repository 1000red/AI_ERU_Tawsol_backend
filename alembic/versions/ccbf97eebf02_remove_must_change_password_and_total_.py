"""remove must_change_password and total_hours

Revision ID: ccbf97eebf02
Revises:
Create Date: 2026-05-22 19:21:56.236945

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccbf97eebf02'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Drop all FKs referencing material.material_id so we can change its type
    op.drop_constraint('announcements_material_id_fkey', 'announcements', type_='foreignkey')
    op.drop_constraint('assignments_material_id_fkey', 'assignments', type_='foreignkey')
    op.drop_constraint('material_files_material_id_fkey', 'material_files', type_='foreignkey')
    op.drop_constraint('material_student_material_id_fkey', 'material_student', type_='foreignkey')
    op.drop_constraint('material_teacher_material_id_fkey', 'material_teacher', type_='foreignkey')
    op.drop_constraint('complaints_material_id_fkey', 'complaints', type_='foreignkey')

    # Step 2: Change material.material_id from INTEGER to VARCHAR(10)
    op.alter_column('material', 'material_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=10),
               existing_nullable=False,
               existing_server_default=sa.text("nextval('material_material_id_seq'::regclass)"),
               postgresql_using='material_id::character varying')

    # Step 3: Change all FK columns that reference material.material_id
    op.alter_column('material_student', 'material_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=10),
               existing_nullable=False,
               postgresql_using='material_id::character varying')
    op.alter_column('material_teacher', 'material_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=10),
               existing_nullable=False,
               postgresql_using='material_id::character varying')
    op.alter_column('complaints', 'material_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=10),
               existing_nullable=False,
               postgresql_using='material_id::character varying')

    # Step 4: Recreate FKs for material_student, material_teacher, complaints
    op.create_foreign_key('material_student_material_id_fkey', 'material_student', 'material', ['material_id'], ['material_id'])
    op.create_foreign_key('material_teacher_material_id_fkey', 'material_teacher', 'material', ['material_id'], ['material_id'])
    op.create_foreign_key('complaints_material_id_fkey', 'complaints', 'material', ['material_id'], ['material_id'])

    # Step 5: Add new columns and other material changes
    op.add_column('material', sa.Column('profile_picture', sa.String(length=255), nullable=True))
    op.alter_column('material', 'duration',
               existing_type=sa.INTEGER(),
               nullable=False)

    # Step 6: Add new columns to announcements and create new FKs
    op.add_column('announcements', sa.Column('announcement_type', sa.String(length=20), nullable=False))
    op.add_column('announcements', sa.Column('priority', sa.String(length=10), nullable=False))
    op.add_column('announcements', sa.Column('target_type', sa.String(length=20), nullable=False))
    op.add_column('announcements', sa.Column('target_course_id', sa.String(length=10), nullable=True))
    op.add_column('announcements', sa.Column('target_department', sa.String(length=100), nullable=True))
    op.add_column('announcements', sa.Column('target_year', sa.Integer(), nullable=True))
    op.add_column('announcements', sa.Column('target_student_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'announcements', 'material', ['target_course_id'], ['material_id'])
    op.create_foreign_key(None, 'announcements', 'users', ['target_student_id'], ['user_id'])
    op.drop_column('announcements', 'material_id')

    # Step 7: assignment_submissions and assignments changes
    op.add_column('assignment_submissions', sa.Column('text_content', sa.Text(), nullable=True))
    op.add_column('assignments', sa.Column('announcement_id', sa.Integer(), nullable=True))
    op.add_column('assignments', sa.Column('text_content', sa.Text(), nullable=True))
    op.create_foreign_key(None, 'assignments', 'announcements', ['announcement_id'], ['announcement_id'])

    # Step 8: chat_history changes
    op.add_column('chat_history', sa.Column('message_type', sa.String(length=10), nullable=False))
    op.add_column('chat_history', sa.Column('file_url', sa.String(length=500), nullable=True))
    op.add_column('chat_history', sa.Column('file_name', sa.String(length=255), nullable=True))
    op.add_column('chat_history', sa.Column('file_size_bytes', sa.Integer(), nullable=True))
    op.add_column('chat_history', sa.Column('voice_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('chat_history', sa.Column('status', sa.String(length=10), nullable=False))
    op.alter_column('chat_history', 'message',
               existing_type=sa.TEXT(),
               nullable=True)

    # Step 9: material_files changes
    op.add_column('material_files', sa.Column('announcement_id', sa.Integer(), nullable=True))
    op.add_column('material_files', sa.Column('text_content', sa.Text(), nullable=True))
    op.create_foreign_key(None, 'material_files', 'announcements', ['announcement_id'], ['announcement_id'])

    # Step 10: users changes
    op.alter_column('users', 'level',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'total_hours')


def downgrade() -> None:
    op.add_column('users', sa.Column('total_hours', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=True))
    op.add_column('users', sa.Column('must_change_password', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.alter_column('users', 'level',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint(None, 'material_files', type_='foreignkey')
    op.drop_column('material_files', 'text_content')
    op.drop_column('material_files', 'announcement_id')
    op.alter_column('chat_history', 'message',
               existing_type=sa.TEXT(),
               nullable=False)
    op.drop_column('chat_history', 'status')
    op.drop_column('chat_history', 'voice_duration_seconds')
    op.drop_column('chat_history', 'file_size_bytes')
    op.drop_column('chat_history', 'file_name')
    op.drop_column('chat_history', 'file_url')
    op.drop_column('chat_history', 'message_type')
    op.drop_constraint(None, 'assignments', type_='foreignkey')
    op.drop_column('assignments', 'text_content')
    op.drop_column('assignments', 'announcement_id')
    op.drop_column('assignment_submissions', 'text_content')
    op.add_column('announcements', sa.Column('material_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'announcements', type_='foreignkey')
    op.drop_constraint(None, 'announcements', type_='foreignkey')
    op.create_foreign_key('announcements_material_id_fkey', 'announcements', 'material', ['material_id'], ['material_id'])
    op.drop_column('announcements', 'target_student_id')
    op.drop_column('announcements', 'target_year')
    op.drop_column('announcements', 'target_department')
    op.drop_column('announcements', 'target_course_id')
    op.drop_column('announcements', 'target_type')
    op.drop_column('announcements', 'priority')
    op.drop_column('announcements', 'announcement_type')
    op.alter_column('material', 'duration',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_column('material', 'profile_picture')
    op.drop_constraint('complaints_material_id_fkey', 'complaints', type_='foreignkey')
    op.drop_constraint('material_teacher_material_id_fkey', 'material_teacher', type_='foreignkey')
    op.drop_constraint('material_student_material_id_fkey', 'material_student', type_='foreignkey')
    op.alter_column('complaints', 'material_id',
               existing_type=sa.String(length=10),
               type_=sa.INTEGER(),
               existing_nullable=False,
               postgresql_using='material_id::integer')
    op.alter_column('material_teacher', 'material_id',
               existing_type=sa.String(length=10),
               type_=sa.INTEGER(),
               existing_nullable=False,
               postgresql_using='material_id::integer')
    op.alter_column('material_student', 'material_id',
               existing_type=sa.String(length=10),
               type_=sa.INTEGER(),
               existing_nullable=False,
               postgresql_using='material_id::integer')
    op.alter_column('material', 'material_id',
               existing_type=sa.String(length=10),
               type_=sa.INTEGER(),
               existing_nullable=False,
               existing_server_default=sa.text("nextval('material_material_id_seq'::regclass)"),
               postgresql_using='material_id::integer')
    op.create_foreign_key('material_student_material_id_fkey', 'material_student', 'material', ['material_id'], ['material_id'])
    op.create_foreign_key('material_teacher_material_id_fkey', 'material_teacher', 'material', ['material_id'], ['material_id'])
    op.create_foreign_key('complaints_material_id_fkey', 'complaints', 'material', ['material_id'], ['material_id'])
    op.create_foreign_key('announcements_material_id_fkey', 'announcements', 'material', ['material_id'], ['material_id'])

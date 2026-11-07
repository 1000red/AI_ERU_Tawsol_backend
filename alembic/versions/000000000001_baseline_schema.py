"""baseline: full pre-chain schema for fresh databases

Revision ID: 000000000001
Revises:
Create Date: 2026-11-07

Background
----------
The historical chain in ``alembic/versions`` starts at ``ccbf97eebf02``, which
only ALTERS tables that already existed: this project originally bootstrapped
its schema with ``Base.metadata.create_all()``, never with Alembic (no
``alembic_version`` table was ever found in the legacy database dump).  As a
result, ``alembic upgrade head`` on an empty database failed immediately at the
root revision ("relation \"announcements\" does not exist").

This baseline creates the exact pre-chain ("legacy") schema that
``ccbf97eebf02`` and its descendants expect, so the entire historical chain can
run on a fresh database and land on the current SQLAlchemy models.  This has
been verified locally: after ``alembic upgrade head`` from this baseline,
``alembic check`` reports "No new upgrade operations detected."

Safety
------
* The SQL only ever runs when NONE of the application tables exist.
* It never drops, truncates, or alters existing objects.
* If application tables already exist (e.g. created by ``create_all()`` on
  application start), the migration aborts with instructions to stamp the
  database instead: ``alembic stamp d25ea49a9110``.

The legacy-only tables (``complaints``, ``assignment_submissions``,
``device_tokens``, ``app_notifications``, ``blacklisted_tokens``) are part of
this baseline because later revisions in the chain drop them; they are not in
the current models.
"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '000000000001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table the baseline is allowed to create. If any of them already exists
# the target database is not fresh and this migration must not proceed.
BASELINE_TABLES = [
    "announcement_reads",
    "announcement_target_users",
    "announcements",
    "app_notifications",
    "assignment_submissions",
    "assignments",
    "blacklisted_tokens",
    "chat_history",
    "complaints",
    "device_tokens",
    "material",
    "material_files",
    "material_student",
    "material_teacher",
    "pinned_conversations",
    "user_type",
    "users",
]

_SQL_FILE = os.path.join(os.path.dirname(__file__), "000000000001_baseline_schema.sql")


def upgrade() -> None:
    bind = op.get_bind()
    if bind is not None:  # skip the guard in offline (--sql) mode
        rows = bind.execute(
            sa.text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = ANY(:names)"
            ),
            {"names": BASELINE_TABLES},
        ).fetchall()
        if rows:
            existing = ", ".join(sorted(r[0] for r in rows))
            raise RuntimeError(
                "Baseline migration 000000000001 refused to run: application "
                f"tables already exist ({existing}). This database is not "
                "fresh. If its schema matches the current models, mark the "
                "migration history as applied instead:\n"
                "    alembic stamp d25ea49a9110\n"
                "Do not run the baseline against a database that holds data."
            )

    with open(_SQL_FILE, encoding="utf-8") as handle:
        for statement in handle.read().split(";"):
            if statement.strip():
                op.execute(statement)


def downgrade() -> None:
    # The baseline only exists for fresh databases. Downgrading past it would
    # require dropping every table, so refuse instead of destroying data.
    raise RuntimeError(
        "Downgrading past the baseline (000000000001) would drop the entire "
        "schema; refused. Drop the database manually if that is truly intended."
    )

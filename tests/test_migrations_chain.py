"""Offline integrity checks for the Alembic migration chain.

These tests require no database connection: they only inspect the revision
scripts under alembic/versions.
"""

import os
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_REV = "000000000001"
EXPECTED_HEAD = "d25ea49a9110"


class TestMigrationChain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
        cls.script = ScriptDirectory.from_config(cfg)

    def test_single_head(self):
        """The chain must stay linear with exactly one head."""
        heads = self.script.get_heads()
        self.assertEqual(heads, [EXPECTED_HEAD])

    def test_baseline_is_root(self):
        """Baseline is the only revision without a parent."""
        roots = self.script.get_bases()
        self.assertEqual(roots, [BASELINE_REV])

    def test_all_revisions_linear(self):
        """Every revision has at most one down_revision (no branching)."""
        revisions = list(self.script.walk_revisions())
        for rev in revisions:
            down = rev.down_revision
            if down is None:
                self.assertEqual(rev.revision, BASELINE_REV)
            elif isinstance(down, (list, tuple)):
                self.fail(f"Branching revision {rev.revision} has multiple parents")

    def test_baseline_revision_present(self):
        rev = self.script.get_revision(BASELINE_REV)
        self.assertIsNotNone(rev)
        self.assertEqual(rev.revision, BASELINE_REV)


if __name__ == "__main__":
    unittest.main()

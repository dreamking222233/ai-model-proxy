"""Regression tests for the lifetime API key cost counter precision."""

import re
import unittest
from pathlib import Path

from app.models.user import UserApiKey


BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent


class UserApiKeyTotalCostSchemaTest(unittest.TestCase):
    def test_orm_uses_lifetime_counter_precision(self):
        column_type = UserApiKey.__table__.c.total_cost.type

        self.assertEqual(column_type.precision, 20)
        self.assertEqual(column_type.scale, 6)

    def test_initialization_sql_uses_lifetime_counter_precision(self):
        sql_files = (
            BACKEND_DIR / "sql" / "init.sql",
            BACKEND_DIR / "sql" / "initData.sql",
            REPO_ROOT / "sql" / "initData.sql",
        )

        for sql_file in sql_files:
            with self.subTest(sql_file=sql_file):
                sql = sql_file.read_text(encoding="utf-8")
                table_match = re.search(
                    r"CREATE TABLE `user_api_key` \((.*?)\n\)",
                    sql,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                self.assertIsNotNone(table_match)
                self.assertRegex(
                    table_match.group(1),
                    re.compile(
                        r"`total_cost`\s+decimal\(20\s*,\s*6\)",
                        flags=re.IGNORECASE,
                    ),
                )

    def test_upgrade_sql_is_guarded_and_targets_lifetime_precision(self):
        upgrade_sql = (
            BACKEND_DIR / "sql" / "upgrade_user_api_key_total_cost_20260814.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("information_schema.columns", upgrade_sql)
        self.assertIn("data_type <> 'decimal'", upgrade_sql)
        self.assertIn("numeric_precision IS NULL", upgrade_sql)
        self.assertIn("numeric_precision < 20", upgrade_sql)
        self.assertIn("SET SESSION lock_wait_timeout = 15", upgrade_sql)
        self.assertRegex(
            upgrade_sql,
            re.compile(
                r"MODIFY COLUMN `total_cost`\s+DECIMAL\(20\s*,\s*6\)",
                flags=re.IGNORECASE,
            ),
        )


if __name__ == "__main__":
    unittest.main()

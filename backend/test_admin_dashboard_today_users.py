"""Regression tests for admin dashboard active/new user statistics."""

import math
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.admin.system import get_dashboard_stats
from app.database import Base
from app.models.log import ConsumptionRecord, RequestLog
from app.models.model import UnifiedModel
from app.models.user import SysUser
from app.services.log_service import LogService


START = datetime(2026, 7, 15, 0, 0, 0)
NOW = datetime(2026, 7, 15, 12, 0, 0)


def _to_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _register_mysql_compat_functions(dbapi_connection, _connection_record):
    dbapi_connection.create_function("concat", -1, lambda *values: "".join(str(value) for value in values))
    dbapi_connection.create_function("date_format", 2, lambda value, pattern: _to_datetime(value).strftime(pattern))
    dbapi_connection.create_function("hour", 1, lambda value: _to_datetime(value).hour)
    dbapi_connection.create_function("floor", 1, math.floor)
    dbapi_connection.create_function(
        "lpad",
        3,
        lambda value, length, pad: str(value).rjust(int(length), str(pad)),
    )
    dbapi_connection.create_function("IF", 3, lambda condition, yes, no: yes if condition else no)


class AdminDashboardTodayUsersTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        event.listen(self.engine, "connect", _register_mysql_compat_functions)
        Base.metadata.create_all(
            self.engine,
            tables=[
                SysUser.__table__,
                RequestLog.__table__,
                ConsumptionRecord.__table__,
                UnifiedModel.__table__,
            ],
        )
        self.db = sessionmaker(bind=self.engine)()
        self._seed_data()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _seed_data(self):
        self.db.add_all([
            self._user(1, "today-user-1", "user", datetime(2026, 7, 15, 1, 0)),
            self._user(2, "today-user-2", "user", datetime(2026, 7, 15, 3, 0)),
            self._user(3, "old-user", "user", datetime(2026, 7, 14, 9, 0)),
            self._user(4, "today-agent", "agent", datetime(2026, 7, 15, 4, 0)),
            self._user(5, "future-user", "user", datetime(2026, 7, 15, 13, 0)),
            self._user(6, "new-without-request", "user", datetime(2026, 7, 15, 7, 0)),
        ])
        self.db.add(UnifiedModel(id=1, model_name="test-model"))
        self.db.add_all([
            self._request(1, 1, datetime(2026, 7, 15, 1, 10), 100, "success"),
            self._request(2, 1, datetime(2026, 7, 15, 1, 20), 0, "failed"),
            self._request(3, 2, datetime(2026, 7, 15, 3, 0), 200, "success"),
            self._request(4, 3, datetime(2026, 7, 14, 23, 0), 300, "success"),
            self._request(5, 4, datetime(2026, 7, 15, 4, 10), 400, "success"),
            self._request(6, None, datetime(2026, 7, 15, 5, 10), 500, "success"),
            self._request(7, 5, datetime(2026, 7, 15, 13, 10), 900, "success"),
        ])
        self.db.add_all([
            self._consumption(1, 1, datetime(2026, 7, 15, 1, 10), "0.300000"),
            self._consumption(2, 5, datetime(2026, 7, 15, 13, 10), "9.000000"),
        ])
        self.db.commit()

    @staticmethod
    def _user(user_id, username, role, created_at, agent_id=None):
        return SysUser(
            id=user_id,
            username=username,
            email=f"{username}@example.com",
            password_hash="hash",
            role=role,
            agent_id=agent_id,
            status=1,
            created_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
    def _request(request_id, user_id, created_at, total_tokens, status, agent_id=None):
        return RequestLog(
            id=request_id,
            request_id=f"request-{request_id}",
            user_id=user_id,
            agent_id=agent_id,
            total_tokens=total_tokens,
            input_tokens=total_tokens,
            output_tokens=0,
            status=status,
            created_at=created_at,
        )

    @staticmethod
    def _consumption(record_id, user_id, created_at, total_cost):
        amount = Decimal(total_cost)
        return ConsumptionRecord(
            id=record_id,
            user_id=user_id,
            request_id=f"request-{record_id}",
            model_name="test-model",
            input_cost=amount,
            output_cost=Decimal("0"),
            total_cost=amount,
            balance_before=Decimal("10.000000"),
            balance_after=Decimal("10.000000") - amount,
            created_at=created_at,
        )

    def test_dashboard_counts_distinct_active_users_and_today_new_users(self):
        with patch.object(LogService, "_get_timezone_day_window", return_value=(START, NOW)):
            response = get_dashboard_stats(
                range_key="7d",
                db=self.db,
                current_user=SysUser(id=99, role="admin"),
            )

        self.assertEqual(5, response.data["user_total"])
        self.assertEqual(3, response.data["today_new_users"])
        self.assertEqual(2, response.data["today_active_users"])
        self.assertEqual(5, response.data["today_requests"])
        self.assertEqual(1200, response.data["today_tokens"])
        self.assertEqual(0.3, response.data["today_cost"])

    def test_dashboard_includes_exact_boundaries_and_excludes_future_rows(self):
        self.db.add_all([
            self._user(7, "start-boundary", "user", START),
            self._user(8, "end-boundary", "user", NOW),
            self._request(8, 7, START, 10, "success"),
            self._request(9, 8, NOW, 20, "success"),
            self._consumption(8, 7, START, "0.100000"),
            self._consumption(9, 8, NOW, "0.300000"),
        ])
        self.db.commit()

        with patch.object(LogService, "_get_timezone_day_window", return_value=(START, NOW)):
            response = get_dashboard_stats(
                range_key="7d",
                db=self.db,
                current_user=SysUser(id=99, role="admin"),
            )

        self.assertEqual(5, response.data["today_new_users"])
        self.assertEqual(4, response.data["today_active_users"])
        self.assertEqual(7, response.data["today_requests"])
        self.assertEqual(1230, response.data["today_tokens"])
        self.assertEqual(0.7, response.data["today_cost"])

    def test_today_detail_buckets_include_active_and_new_users(self):
        with patch.object(LogService, "_get_timezone_day_window", return_value=(START, NOW)):
            rows = LogService.get_request_stats(self.db, range_key="today")

        self.assertEqual(12, len(rows))
        self.assertEqual(2, rows[0]["total_requests"])
        self.assertEqual(1, rows[0]["active_users"])
        self.assertEqual(1, rows[0]["new_users"])
        self.assertEqual(1, rows[1]["active_users"])
        self.assertEqual(1, rows[1]["new_users"])
        self.assertEqual(2, rows[2]["total_requests"])
        self.assertEqual(0, rows[2]["active_users"])
        self.assertEqual(0, rows[2]["new_users"])
        self.assertEqual(0, rows[3]["total_requests"])
        self.assertEqual(0, rows[3]["active_users"])
        self.assertEqual(1, rows[3]["new_users"])

    def test_daily_detail_uses_same_role_and_distinct_user_rules(self):
        with patch.object(
            LogService,
            "_get_timezone_day_window",
            return_value=(datetime(2026, 7, 9, 0, 0), NOW),
        ):
            rows = LogService.get_request_stats(self.db, range_key="7d")

        today_row = rows[-1]
        self.assertEqual("2026-07-15", today_row["date"])
        self.assertEqual(5, today_row["total_requests"])
        self.assertEqual(2, today_row["active_users"])
        self.assertEqual(3, today_row["new_users"])

    def test_same_user_is_active_in_each_two_hour_bucket_used(self):
        self.db.add(self._request(40, 1, datetime(2026, 7, 15, 3, 30), 50, "success"))
        self.db.commit()

        with patch.object(LogService, "_get_timezone_day_window", return_value=(START, NOW)):
            rows = LogService.get_request_stats(self.db, range_key="today")

        self.assertEqual(1, rows[0]["active_users"])
        self.assertEqual(2, rows[1]["active_users"])

    def test_agent_stats_isolate_active_and_new_users(self):
        self.db.add_all([
            self._user(30, "agent-1-user", "user", datetime(2026, 7, 15, 8, 0), agent_id=1),
            self._user(31, "agent-2-user", "user", datetime(2026, 7, 15, 8, 10), agent_id=2),
            self._request(30, 30, datetime(2026, 7, 15, 8, 20), 100, "success", agent_id=1),
            self._request(31, 31, datetime(2026, 7, 15, 8, 30), 100, "success", agent_id=2),
        ])
        self.db.commit()

        with patch.object(LogService, "_get_timezone_day_window", return_value=(START, NOW)):
            rows = LogService.get_request_stats(self.db, range_key="today", agent_id=1)

        self.assertEqual(1, sum(row["active_users"] for row in rows))
        self.assertEqual(1, sum(row["new_users"] for row in rows))
        self.assertEqual(1, sum(row["total_requests"] for row in rows))

    def test_daily_bucket_keeps_new_users_on_a_day_without_requests(self):
        self.db.add(self._user(32, "july-13-new-user", "user", datetime(2026, 7, 13, 10, 0)))
        self.db.commit()

        with patch.object(
            LogService,
            "_get_timezone_day_window",
            return_value=(datetime(2026, 7, 9, 0, 0), NOW),
        ):
            rows = LogService.get_request_stats(self.db, range_key="7d")

        july_13 = next(row for row in rows if row["date"] == "2026-07-13")
        self.assertEqual(0, july_13["total_requests"])
        self.assertEqual(0, july_13["active_users"])
        self.assertEqual(1, july_13["new_users"])


if __name__ == "__main__":
    unittest.main()

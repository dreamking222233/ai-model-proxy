import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.services.log_service import LogService


class AdminDashboardStatsTest(unittest.TestCase):
    @patch(
        "app.services.log_service.LogService._get_timezone_day_window",
        return_value=(datetime(2026, 4, 30, 0, 0, 0), datetime(2026, 4, 30, 12, 0, 0)),
    )
    def test_resolve_request_stats_config_today_uses_two_hour_buckets(self, mock_day_window):
        config = LogService._resolve_request_stats_config(days=7, range_key="today")

        self.assertEqual(config["range_key"], "today")
        self.assertEqual(config["days"], 1)
        self.assertEqual(config["bucket_mode"], "two_hour")
        self.assertEqual(config["since"], datetime(2026, 4, 30, 0, 0, 0))
        self.assertEqual(config["until"], datetime(2026, 4, 30, 12, 0, 0))
        mock_day_window.assert_called_once_with(1)

    @patch(
        "app.services.log_service.LogService._get_timezone_day_window",
        return_value=(datetime(2026, 4, 1, 0, 0, 0), datetime(2026, 4, 30, 12, 0, 0)),
    )
    def test_resolve_request_stats_config_uses_requested_range_days(self, mock_day_window):
        config = LogService._resolve_request_stats_config(days=7, range_key="30d")

        self.assertEqual(config["range_key"], "30d")
        self.assertEqual(config["days"], 30)
        self.assertEqual(config["bucket_mode"], "day")
        mock_day_window.assert_called_once_with(30)

    def test_summarize_model_usage_rows_collapses_remaining_models(self):
        rows = [
            SimpleNamespace(model_name="gpt-4o", request_count=20, total_tokens=2000),
            SimpleNamespace(model_name="claude-3-7-sonnet", request_count=15, total_tokens=1500),
            SimpleNamespace(model_name="gpt-4.1", request_count=10, total_tokens=1000),
            SimpleNamespace(model_name="gemini-2.5-pro", request_count=5, total_tokens=500),
        ]

        result = LogService._summarize_model_usage_rows(rows, limit=3)

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["model_name"], "gpt-4o")
        self.assertEqual(result[0]["ratio"], 40.0)
        self.assertEqual(result[-1]["model_name"], "其他")
        self.assertEqual(result[-1]["request_count"], 5)
        self.assertEqual(result[-1]["total_tokens"], 500)
        self.assertEqual(result[-1]["ratio"], 10.0)


if __name__ == "__main__":
    unittest.main()

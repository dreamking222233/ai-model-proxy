import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI

from app.api.user import stats as user_stats_api
from app.services.log_service import LogService


class UserStatsRankingApiTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = MagicMock()
        self.app = FastAPI()
        self.app.include_router(user_stats_api.router)
        self.app.dependency_overrides[user_stats_api.get_db] = lambda: self.db
        self.app.dependency_overrides[user_stats_api.get_current_user] = lambda: SimpleNamespace(id=1)

    async def get(self, path: str):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    @patch("app.api.user.stats.LogService.get_token_ranking")
    async def test_token_ranking_defaults_to_top_10(self, mock_get_ranking):
        mock_get_ranking.return_value = []

        response = await self.get("/api/user/stats/token-ranking?days=7")

        self.assertEqual(response.status_code, 200)
        mock_get_ranking.assert_called_once_with(self.db, 7, 10)
        self.assertEqual(response.json()["data"]["days"], 7)
        self.assertEqual(response.json()["data"]["limit"], 10)

    @patch("app.api.user.stats.LogService.get_token_ranking")
    async def test_token_ranking_passes_requested_days_and_limit(self, mock_get_ranking):
        mock_get_ranking.return_value = [{"rank": 1, "user_id": 1, "total_tokens": 100}]

        response = await self.get("/api/user/stats/token-ranking?days=30&limit=10")

        self.assertEqual(response.status_code, 200)
        mock_get_ranking.assert_called_once_with(self.db, 30, 10)
        data = response.json()["data"]
        self.assertEqual(data["days"], 30)
        self.assertEqual(data["limit"], 10)
        self.assertEqual(len(data["ranking"]), 1)

    @patch("app.api.user.stats.LogService.get_token_ranking")
    async def test_token_ranking_rejects_invalid_limit(self, mock_get_ranking):
        too_small = await self.get("/api/user/stats/token-ranking?limit=0")
        too_large = await self.get("/api/user/stats/token-ranking?limit=51")

        self.assertEqual(too_small.status_code, 422)
        self.assertEqual(too_large.status_code, 422)
        mock_get_ranking.assert_not_called()


class LogServiceTokenRankingTest(unittest.TestCase):
    def make_db(self):
        db = MagicMock()
        query = MagicMock()
        query.join.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = []
        db.query.return_value = query
        return db, query

    @patch(
        "app.services.log_service.LogService._get_timezone_day_window",
        return_value=(datetime(2026, 5, 3, 0, 0, 0), datetime(2026, 5, 3, 12, 0, 0)),
    )
    def test_token_ranking_service_defaults_to_top_10(self, _mock_window):
        db, query = self.make_db()

        LogService.get_token_ranking(db)

        query.limit.assert_called_once_with(10)

    @patch(
        "app.services.log_service.LogService._get_timezone_day_window",
        return_value=(datetime(2026, 5, 3, 0, 0, 0), datetime(2026, 5, 3, 12, 0, 0)),
    )
    def test_token_ranking_service_clamps_limit(self, _mock_window):
        db, too_large_query = self.make_db()
        LogService.get_token_ranking(db, limit=1000)

        too_large_query.limit.assert_called_once_with(50)

        db, too_small_query = self.make_db()
        LogService.get_token_ranking(db, limit=0)

        too_small_query.limit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()

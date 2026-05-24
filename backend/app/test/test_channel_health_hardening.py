import asyncio
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.health_service import HealthService


def _build_query_returning(obj):
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = obj
    return query


def _mock_system_config(_db, key, default=None):
    values = {
        "circuit_breaker_recovery": 600,
        "circuit_breaker_threshold": 5,
        "health_check_circuit_breaker_threshold": 8,
        "health_check_recent_success_grace_seconds": 1800,
    }
    return values.get(key, default)


class ChannelHealthHardeningTest(unittest.TestCase):
    @patch("app.services.health_service.get_system_config", side_effect=_mock_system_config)
    @patch("app.services.health_service.session_scope")
    @patch("app.services.health_service.HealthService._do_health_check")
    def test_recent_live_success_softens_scheduled_failure(
        self,
        mock_do_health_check,
        mock_session_scope,
        _mock_get_system_config,
    ):
        mock_do_health_check.return_value = (False, 123, "timeout")

        now = datetime.utcnow()
        persisted_channel = SimpleNamespace(
            id=7,
            name="channel-a",
            is_healthy=1,
            health_score=100,
            failure_count=0,
            last_success_at=now - timedelta(minutes=5),
            last_failure_at=None,
            circuit_breaker_until=None,
        )
        write_db = MagicMock()
        write_db.query.return_value = _build_query_returning(persisted_channel)
        mock_session_scope.return_value = nullcontext(write_db)

        channel = SimpleNamespace(id=7, name="channel-a")

        result = asyncio.run(HealthService._check_and_record(channel, "gpt-4o-mini"))

        self.assertTrue(result["is_healthy"])
        self.assertFalse(result["probe_success"])
        self.assertTrue(result["recent_live_success"])
        self.assertEqual(persisted_channel.failure_count, 0)
        self.assertEqual(persisted_channel.health_score, 95)
        self.assertIsNone(persisted_channel.circuit_breaker_until)
        self.assertIsNotNone(persisted_channel.last_failure_at)

    @patch("app.services.health_service.get_system_config", side_effect=_mock_system_config)
    @patch("app.services.health_service.session_scope")
    @patch("app.services.health_service.HealthService._do_health_check")
    def test_stale_channel_health_failure_uses_higher_health_threshold_before_breaking(
        self,
        mock_do_health_check,
        mock_session_scope,
        _mock_get_system_config,
    ):
        mock_do_health_check.return_value = (False, 456, "upstream down")

        now = datetime.utcnow()
        persisted_channel = SimpleNamespace(
            id=8,
            name="channel-b",
            is_healthy=1,
            health_score=80,
            failure_count=7,
            last_success_at=now - timedelta(hours=2),
            last_failure_at=None,
            circuit_breaker_until=None,
        )
        write_db = MagicMock()
        write_db.query.return_value = _build_query_returning(persisted_channel)
        mock_session_scope.return_value = nullcontext(write_db)

        channel = SimpleNamespace(id=8, name="channel-b")

        result = asyncio.run(HealthService._check_and_record(channel, "gpt-4o-mini"))

        self.assertFalse(result["is_healthy"])
        self.assertFalse(result["probe_success"])
        self.assertFalse(result["recent_live_success"])
        self.assertEqual(persisted_channel.failure_count, 8)
        self.assertEqual(persisted_channel.health_score, 70)
        self.assertIsNotNone(persisted_channel.circuit_breaker_until)

    @patch("app.services.health_service.get_system_config", side_effect=_mock_system_config)
    @patch("app.services.health_service.session_scope")
    @patch("app.services.health_service.HealthService._do_health_check")
    def test_health_check_success_does_not_overwrite_last_live_success_time(
        self,
        mock_do_health_check,
        mock_session_scope,
        _mock_get_system_config,
    ):
        mock_do_health_check.return_value = (True, 88, None)

        last_live_success_at = datetime.utcnow() - timedelta(hours=1)
        persisted_channel = SimpleNamespace(
            id=9,
            name="channel-c",
            is_healthy=0,
            health_score=50,
            failure_count=3,
            last_success_at=last_live_success_at,
            last_failure_at=None,
            circuit_breaker_until=datetime.utcnow() + timedelta(minutes=5),
        )
        write_db = MagicMock()
        write_db.query.return_value = _build_query_returning(persisted_channel)
        mock_session_scope.return_value = nullcontext(write_db)

        channel = SimpleNamespace(id=9, name="channel-c")

        result = asyncio.run(HealthService._check_and_record(channel, "gpt-4o-mini", check_source="manual"))

        self.assertTrue(result["is_healthy"])
        self.assertTrue(result["probe_success"])
        self.assertEqual(persisted_channel.failure_count, 0)
        self.assertEqual(persisted_channel.health_score, 60)
        self.assertIsNone(persisted_channel.circuit_breaker_until)
        self.assertEqual(persisted_channel.last_success_at, last_live_success_at)


if __name__ == "__main__":
    unittest.main()

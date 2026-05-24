import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from app.services.proxy_service import ProxyService


def _build_query_returning(obj):
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = obj
    return query


def _mock_system_config(_db, key, default=None):
    values = {
        "circuit_breaker_threshold": 5,
        "circuit_breaker_recovery": 600,
        "transient_channel_failure_threshold": None,
        "transient_channel_failure_recovery": None,
        "transient_channel_failure_health_penalty": 5,
    }
    return values.get(key, default)


class ProxyChannelFailureHardeningTest(unittest.TestCase):
    @patch("app.services.proxy_service.get_system_config", side_effect=_mock_system_config)
    @patch("app.services.proxy_service.session_scope")
    def test_transient_http_failure_uses_softer_threshold_and_shorter_recovery(
        self,
        mock_session_scope,
        _mock_get_system_config,
    ):
        persisted_channel = SimpleNamespace(
            id=7,
            name="channel-a",
            failure_count=6,
            health_score=100,
            is_healthy=1,
            last_failure_at=None,
            circuit_breaker_until=None,
        )
        write_db = MagicMock()
        write_db.query.return_value = _build_query_returning(persisted_channel)
        mock_session_scope.return_value = nullcontext(write_db)

        before = datetime.utcnow()
        ProxyService._record_channel_failure(
            db=MagicMock(),
            channel=SimpleNamespace(id=7, name="channel-a"),
            exc=Exception("Upstream returned HTTP 429: rate limit exceeded"),
        )

        self.assertEqual(persisted_channel.failure_count, 7)
        self.assertEqual(persisted_channel.health_score, 95)
        self.assertEqual(persisted_channel.is_healthy, 0)
        self.assertIsNotNone(persisted_channel.circuit_breaker_until)
        self.assertGreaterEqual(
            persisted_channel.circuit_breaker_until,
            before + timedelta(seconds=100),
        )
        self.assertLessEqual(
            persisted_channel.circuit_breaker_until,
            before + timedelta(seconds=130),
        )

    @patch("app.services.proxy_service.get_system_config", side_effect=_mock_system_config)
    @patch("app.services.proxy_service.session_scope")
    def test_transport_timeout_is_classified_as_transient_failure(
        self,
        mock_session_scope,
        _mock_get_system_config,
    ):
        persisted_channel = SimpleNamespace(
            id=8,
            name="channel-b",
            failure_count=0,
            health_score=90,
            is_healthy=1,
            last_failure_at=None,
            circuit_breaker_until=None,
        )
        write_db = MagicMock()
        write_db.query.return_value = _build_query_returning(persisted_channel)
        mock_session_scope.return_value = nullcontext(write_db)

        ProxyService._record_channel_failure(
            db=MagicMock(),
            channel=SimpleNamespace(id=8, name="channel-b"),
            exc=httpx.ReadTimeout("upstream timed out"),
        )

        self.assertEqual(persisted_channel.failure_count, 1)
        self.assertEqual(persisted_channel.health_score, 85)
        self.assertEqual(persisted_channel.is_healthy, 1)
        self.assertIsNone(persisted_channel.circuit_breaker_until)

    @patch("app.services.proxy_service.get_system_config", side_effect=_mock_system_config)
    @patch("app.services.proxy_service.session_scope")
    def test_hard_failure_keeps_base_threshold_and_penalty(
        self,
        mock_session_scope,
        _mock_get_system_config,
    ):
        persisted_channel = SimpleNamespace(
            id=9,
            name="channel-c",
            failure_count=4,
            health_score=100,
            is_healthy=1,
            last_failure_at=None,
            circuit_breaker_until=None,
        )
        write_db = MagicMock()
        write_db.query.return_value = _build_query_returning(persisted_channel)
        mock_session_scope.return_value = nullcontext(write_db)

        before = datetime.utcnow()
        ProxyService._record_channel_failure(
            db=MagicMock(),
            channel=SimpleNamespace(id=9, name="channel-c"),
            exc=Exception("Upstream returned HTTP 401: invalid api key"),
        )

        self.assertEqual(persisted_channel.failure_count, 5)
        self.assertEqual(persisted_channel.health_score, 90)
        self.assertEqual(persisted_channel.is_healthy, 0)
        self.assertIsNotNone(persisted_channel.circuit_breaker_until)
        self.assertGreaterEqual(
            persisted_channel.circuit_breaker_until,
            before + timedelta(seconds=580),
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.channel_service import ChannelService
from app.services.health_service import HealthService


class ChannelHealthMonitorSwitchTest(unittest.TestCase):
    def test_google_channel_defaults_to_health_monitor_disabled(self):
        self.assertEqual(
            ChannelService._resolve_default_health_check_enabled("google", "google-official"),
            0,
        )
        self.assertEqual(
            ChannelService._resolve_default_health_check_enabled("google", "google-vertex-image"),
            0,
        )

    def test_non_google_channel_defaults_to_health_monitor_enabled(self):
        self.assertEqual(
            ChannelService._resolve_default_health_check_enabled("openai", "default"),
            1,
        )

    def test_channel_to_dict_exposes_health_check_enabled(self):
        payload = ChannelService._channel_to_dict(
            SimpleNamespace(
                id=1,
                name="google-image",
                base_url="https://example.com",
                api_key="secret-key-123456",
                protocol_type="google",
                provider_variant="google-official",
                auth_header_type="x-goog-api-key",
                priority=1,
                enabled=1,
                health_check_enabled=0,
                is_healthy=1,
                health_score=100,
                failure_count=0,
                circuit_breaker_until=None,
                health_check_model=None,
                last_health_check_at=None,
                last_success_at=None,
                last_failure_at=None,
                description=None,
                created_at=None,
                updated_at=None,
            )
        )

        self.assertEqual(payload["health_check_enabled"], 0)


class HealthServiceMonitorFilterTest(unittest.TestCase):
    @patch("app.services.health_service.HealthService._list_health_monitored_channels")
    def test_get_health_status_uses_monitored_channel_subset(self, mock_list_channels):
        monitored_channel = SimpleNamespace(
            id=1,
            name="channel-a",
            protocol_type="google",
            health_check_enabled=1,
            is_healthy=1,
            health_score=95,
            failure_count=0,
            health_check_model=None,
            circuit_breaker_until=None,
            last_health_check_at=None,
            last_success_at=None,
            last_failure_at=None,
        )
        mock_list_channels.return_value = [monitored_channel]

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = HealthService.get_health_status(db)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["channel_id"], 1)
        self.assertTrue(result[0]["health_check_enabled"])
        mock_list_channels.assert_called_once_with(db)


if __name__ == "__main__":
    unittest.main()

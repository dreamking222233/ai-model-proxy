import unittest
from decimal import Decimal
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ServiceException
from app.services.proxy_service import ProxyService
from app.services.subscription_service import SubscriptionService


class _FailingScope:
    def __enter__(self):
        raise RuntimeError("db unavailable")

    def __exit__(self, exc_type, exc, tb):
        return False


class ProxyRequestAuditHardeningTest(unittest.TestCase):
    @patch("app.services.proxy_service.ProxyService._log_failed_request", return_value=True)
    @patch("app.services.proxy_service.ProxyService._deduct_balance_and_log")
    @patch("app.services.proxy_service.ProxyService._record_success")
    def test_finalize_successful_text_request_raises_when_non_stream_accounting_fails(
        self,
        mock_record_success,
        mock_deduct_balance_and_log,
        mock_log_failed_request,
    ):
        mock_deduct_balance_and_log.side_effect = RuntimeError("ledger write failed")

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._finalize_successful_text_request(
                db=MagicMock(),
                user=SimpleNamespace(id=1, subscription_type="balance"),
                api_key_record=SimpleNamespace(id=2),
                unified_model=SimpleNamespace(model_name="gpt-4o"),
                request_id="req-ns-1",
                requested_model="gpt-4o",
                input_tokens=100,
                output_tokens=50,
                channel=SimpleNamespace(id=9, name="channel-a", protocol_type="openai"),
                client_ip="127.0.0.1",
                response_time_ms=1234,
                is_stream=False,
                actual_model="gpt-4o-upstream",
                request_type="chat",
                raise_on_failure=True,
            )

        self.assertEqual(ctx.exception.error_code, "TEXT_BILLING_FAILED")
        mock_record_success.assert_called_once()
        mock_log_failed_request.assert_called_once()
        self.assertEqual(mock_log_failed_request.call_args.args[3], "req-ns-1")
        self.assertEqual(mock_log_failed_request.call_args.kwargs["total_tokens"], 150)

    @patch("app.services.proxy_service.ProxyService._log_failed_request", return_value=True)
    @patch("app.services.proxy_service.ProxyService._deduct_balance_and_log")
    @patch("app.services.proxy_service.ProxyService._record_success")
    def test_finalize_successful_text_request_logs_and_swallows_when_stream_accounting_fails(
        self,
        mock_record_success,
        mock_deduct_balance_and_log,
        mock_log_failed_request,
    ):
        mock_deduct_balance_and_log.side_effect = ServiceException(
            403,
            "当日套餐额度已用尽，请明天再试或联系管理员升级套餐",
            "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
        )

        ProxyService._finalize_successful_text_request(
            db=MagicMock(),
            user=SimpleNamespace(id=1, subscription_type="quota"),
            api_key_record=SimpleNamespace(id=2),
            unified_model=SimpleNamespace(model_name="claude-3-7-sonnet"),
            request_id="req-stream-1",
            requested_model="claude-3-7-sonnet",
            input_tokens=300,
            output_tokens=120,
            channel=SimpleNamespace(id=11, name="channel-b", protocol_type="anthropic"),
            client_ip="127.0.0.1",
            response_time_ms=2222,
            is_stream=True,
            actual_model="claude-3-7-sonnet-upstream",
            cache_info={"cache_status": "BYPASS"},
            request_type="chat",
            raise_on_failure=False,
        )

        mock_record_success.assert_called_once()
        mock_log_failed_request.assert_called_once()
        self.assertEqual(mock_log_failed_request.call_args.kwargs["billing_type"], "subscription")

    @patch("app.services.proxy_service.ProxyService._write_minimal_failed_request_log", return_value=True)
    @patch("app.services.proxy_service.session_scope", return_value=_FailingScope())
    def test_log_failed_request_falls_back_to_minimal_log_when_detailed_write_fails(
        self,
        _mock_session_scope,
        mock_write_minimal_failed_request_log,
    ):
        result = ProxyService._log_failed_request(
            db=MagicMock(),
            user=SimpleNamespace(id=1),
            api_key_record=SimpleNamespace(id=2),
            request_id="req-fallback-1",
            requested_model="gpt-4o",
            client_ip="127.0.0.1",
            is_stream=False,
            error_message="local accounting failed",
            channel=SimpleNamespace(id=1, name="channel-a", protocol_type="openai"),
        )

        self.assertTrue(result)
        mock_write_minimal_failed_request_log.assert_called_once()


class SubscriptionCycleRaceRecoveryTest(unittest.TestCase):
    def test_get_or_create_cycle_recovers_after_unique_constraint_conflict(self):
        recovered_cycle = SimpleNamespace(id=10, used_amount=Decimal("0"))
        query = MagicMock()
        query.filter.return_value = query
        query.with_for_update.return_value = query
        query.first.side_effect = [None, recovered_cycle]

        savepoint = MagicMock()
        db = MagicMock()
        db.query.return_value = query
        db.begin_nested.return_value = savepoint
        db.flush.side_effect = IntegrityError("insert", {}, Exception("duplicate"))

        subscription = SimpleNamespace(
            id=5,
            user_id=1,
            reset_timezone="Asia/Shanghai",
            quota_metric="total_tokens",
            quota_value=Decimal("100"),
        )

        cycle = SubscriptionService._get_or_create_cycle(
            db,
            subscription,
            now=datetime(2026, 4, 25, 10, 0, 0),
            lock=True,
        )

        self.assertIs(cycle, recovered_cycle)
        query.with_for_update.assert_called_once()
        savepoint.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()

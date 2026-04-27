import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import ServiceException
from app.core.security import hash_password, verify_password
from app.services.auth_service import AuthService


class AuthServiceForgotPasswordTest(unittest.TestCase):
    def test_verify_password_reset_identity_accepts_valid_identity(self):
        user = SimpleNamespace(status=1, password_hash=hash_password("old-pass-123"))
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = user
        db = MagicMock()
        db.query.return_value = query

        AuthService.verify_password_reset_identity(db, "demo-user", "demo@example.com")

        db.commit.assert_not_called()

    def test_reset_password_by_identity_updates_password_hash(self):
        user = SimpleNamespace(status=1, password_hash=hash_password("old-pass-123"))
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = user
        db = MagicMock()
        db.query.return_value = query

        AuthService.reset_password_by_identity(db, "demo-user", "demo@example.com", "new-pass-456")

        self.assertTrue(verify_password("new-pass-456", user.password_hash))
        self.assertFalse(verify_password("old-pass-123", user.password_hash))
        db.commit.assert_called_once()

    def test_reset_password_by_identity_rejects_mismatched_identity(self):
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = None
        db = MagicMock()
        db.query.return_value = query

        with self.assertRaises(ServiceException) as ctx:
            AuthService.reset_password_by_identity(db, "demo-user", "wrong@example.com", "new-pass-456")

        self.assertEqual(ctx.exception.error_code, "IDENTITY_MISMATCH")
        db.commit.assert_not_called()

    def test_reset_password_by_identity_rejects_disabled_account(self):
        user = SimpleNamespace(status=0, password_hash=hash_password("old-pass-123"))
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = user
        db = MagicMock()
        db.query.return_value = query

        with self.assertRaises(ServiceException) as ctx:
            AuthService.reset_password_by_identity(db, "demo-user", "demo@example.com", "new-pass-456")

        self.assertEqual(ctx.exception.error_code, "ACCOUNT_DISABLED")
        self.assertTrue(verify_password("old-pass-123", user.password_hash))
        db.commit.assert_not_called()

    @patch("app.services.auth_service.AgentService.is_local_dev_host", return_value=False)
    @patch("app.services.auth_service.AgentService.get_site_context_from_request")
    def test_reset_password_by_identity_limits_query_to_agent_site(
        self,
        mock_get_site_context,
        _mock_is_local_dev_host,
    ):
        mock_get_site_context.return_value = SimpleNamespace(site_scope="agent", agent_id=9, host="agent.example.com", request_host="agent.example.com")
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = None
        db = MagicMock()
        db.query.return_value = query

        with self.assertRaises(ServiceException) as ctx:
            AuthService.reset_password_by_identity(
                db,
                "demo-user",
                "demo@example.com",
                "new-pass-456",
                request_host="api.example.com",
                x_site_host="agent.example.com",
            )

        self.assertEqual(ctx.exception.error_code, "IDENTITY_MISMATCH")
        self.assertEqual(query.filter.call_count, 2)
        scope_filter = str(query.filter.call_args_list[1][0][0])
        self.assertIn("sys_user.agent_id", scope_filter)
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()

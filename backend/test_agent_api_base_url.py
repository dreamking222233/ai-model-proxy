"""Regression tests for per-agent API Base URL configuration."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.api.admin.system import ConfigUpdate, update_config
from app.core.dependencies import verify_api_key_from_headers
from app.core.exceptions import ServiceException
from app.database import Base
from app.models.agent import Agent, AgentBalance, AgentImageBalance
from app.models.log import SystemConfig
from app.models.user import SysUser, UserApiKey
from app.services.agent_service import AgentService


class AgentApiBaseUrlTest(unittest.TestCase):
    TABLES = [
        Agent.__table__,
        AgentBalance.__table__,
        AgentImageBalance.__table__,
        SystemConfig.__table__,
        SysUser.__table__,
        UserApiKey.__table__,
    ]

    def setUp(self):
        self.host_settings = patch.multiple(
            settings,
            PLATFORM_FRONTEND_HOSTS=["www.platform.test"],
            PLATFORM_API_HOSTS=["api.platform.test"],
        )
        self.host_settings.start()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=self.TABLES)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(SystemConfig(
            id=1,
            config_key="api_base_url",
            config_value="https://api.platform.test",
            config_type="string",
        ))
        self.agent = Agent(
            id=7,
            agent_code="agent-7",
            agent_name="Agent 7",
            status="active",
            frontend_domain="portal.agent.test",
            quickstart_api_base_url=None,
            api_domain=None,
            allow_self_register=1,
            online_recharge_enabled=1,
            subscription_online_recharge_enabled=1,
            custom_recharge_rate_enabled=0,
            custom_recharge_rate=5,
        )
        self.db.add_all([
            self.agent,
            AgentBalance(id=101, agent_id=7, balance=0),
            AgentImageBalance(id=102, agent_id=7, balance=0),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.host_settings.stop()

    def test_normalize_custom_and_shared_api_base_urls(self):
        custom_url, custom_domain = AgentService.normalize_api_base_url(
            " HTTPS://Api.Agent.Test:8443/ "
        )
        shared_url, shared_domain = AgentService.normalize_api_base_url(
            "https://api.platform.test/"
        )

        self.assertEqual("https://api.agent.test:8443", custom_url)
        self.assertEqual("api.agent.test", custom_domain)
        self.assertEqual("https://api.platform.test", shared_url)
        self.assertIsNone(shared_domain)
        self.assertEqual((None, None), AgentService.normalize_api_base_url(""))
        self.assertEqual(
            ("http://[2001:db8::1]:8085", "2001:db8::1"),
            AgentService.normalize_api_base_url("http://[2001:db8::1]:8085/"),
        )
        self.assertEqual(
            ("http://localhost:8085", None),
            AgentService.normalize_api_base_url("http://localhost:8085", self.db),
        )

    def test_invalid_api_base_urls_are_rejected(self):
        invalid_values = (
            "api.agent.test",
            "ftp://api.agent.test",
            "https://user:pass@api.agent.test",
            "https://api.agent.test/v1",
            "https://api.agent.test?tenant=7",
            "https://www.platform.test",
            "https://[not-an-ipv6-address]",
            f"https://{'.'.join(['a' * 60] * 5)}.test",
        )

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ServiceException) as raised:
                AgentService.normalize_api_base_url(value)
            self.assertEqual("INVALID_AGENT_API_BASE_URL", raised.exception.error_code)

    def test_unconfigured_agent_uses_database_shared_api_url(self):
        result = AgentService.get_agent(self.db, self.agent.id)

        self.assertEqual("https://api.platform.test", result["quickstart_api_base_url"])
        self.assertEqual("", result["configured_quickstart_api_base_url"])
        self.assertTrue(result["uses_shared_api_base_url"])

    def test_admin_update_synchronizes_api_domain_and_can_restore_shared_url(self):
        updated = AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": "https://api.agent.test/"},
        )

        self.assertEqual("https://api.agent.test", updated["quickstart_api_base_url"])
        self.assertEqual("https://api.agent.test", updated["configured_quickstart_api_base_url"])
        self.assertEqual("api.agent.test", updated["api_domain"])
        self.assertFalse(updated["uses_shared_api_base_url"])

        restored = AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": ""},
        )

        self.assertEqual("https://api.platform.test", restored["quickstart_api_base_url"])
        self.assertEqual("", restored["configured_quickstart_api_base_url"])
        self.assertIsNone(restored["api_domain"])
        self.assertTrue(restored["uses_shared_api_base_url"])

    def test_entering_shared_api_url_keeps_dynamic_inheritance(self):
        updated = AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": "https://api.platform.test/"},
        )

        self.assertEqual("https://api.platform.test", updated["quickstart_api_base_url"])
        self.assertEqual("", updated["configured_quickstart_api_base_url"])
        self.assertIsNone(updated["api_domain"])

        config = self.db.query(SystemConfig).filter(SystemConfig.config_key == "api_base_url").first()
        config.config_value = "https://new-shared.test"
        self.db.commit()
        self.assertEqual(
            "https://new-shared.test",
            AgentService.get_agent(self.db, self.agent.id)["quickstart_api_base_url"],
        )

    def test_custom_api_host_resolves_to_owning_agent(self):
        AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": "https://api.agent.test"},
        )

        context = AgentService.get_site_context_from_request(
            self.db,
            host="api.agent.test",
        )

        self.assertEqual("agent", context.site_scope)
        self.assertEqual(self.agent.id, context.agent_id)
        self.assertTrue(context.is_api_host)

    def test_api_key_direct_call_uses_custom_api_host_over_foreign_origin(self):
        import hashlib

        AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": "https://api.agent.test"},
        )
        user = SysUser(
            id=70,
            username="agent-user",
            email="agent-user@example.test",
            password_hash="hash",
            role="user",
            agent_id=self.agent.id,
            status=1,
        )
        raw_key = "sk-agent-api-test"
        key = UserApiKey(
            id=71,
            user_id=user.id,
            name="test",
            key_prefix="sk-agent",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            status="active",
        )
        self.db.add_all([user, key])
        self.db.commit()

        resolved_user, resolved_key = verify_api_key_from_headers(
            self.db,
            authorization=f"Bearer {raw_key}",
            host="api.agent.test",
            origin="https://third-party-client.test",
        )

        self.assertEqual(user.id, resolved_user.id)
        self.assertEqual(key.id, resolved_key.id)

        user.agent_id = None
        self.db.commit()
        with self.assertRaises(ServiceException) as raised:
            verify_api_key_from_headers(
                self.db,
                authorization=f"Bearer {raw_key}",
                host="api.agent.test",
            )
        self.assertEqual("AGENT_SITE_MISMATCH", raised.exception.error_code)

    def test_authenticated_agent_user_receives_agent_url_on_shared_api_host(self):
        AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": "https://api.agent.test"},
        )

        result = AgentService.build_public_site_config(
            self.db,
            host="api.platform.test",
            user=SimpleNamespace(agent_id=self.agent.id),
        )

        self.assertEqual("platform", result["site_scope"])
        self.assertIsNone(result["agent_id"])
        self.assertEqual("https://api.agent.test", result["quickstart_api_base_url"])

    def test_database_shared_api_host_allows_agent_api_key_direct_call(self):
        import hashlib

        config = self.db.query(SystemConfig).filter(SystemConfig.config_key == "api_base_url").first()
        config.config_value = "https://new-shared.test"
        user = SysUser(
            id=70,
            username="shared-api-user",
            email="shared-api-user@example.test",
            password_hash="hash",
            role="user",
            agent_id=self.agent.id,
            status=1,
        )
        raw_key = "sk-database-shared-api-test"
        key = UserApiKey(
            id=71,
            user_id=user.id,
            name="test",
            key_prefix="sk-database",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            status="active",
        )
        self.db.add_all([user, key])
        self.db.commit()

        normalized_url, api_domain = AgentService.normalize_api_base_url(
            "https://new-shared.test/",
            self.db,
        )
        resolved_user, _ = verify_api_key_from_headers(
            self.db,
            authorization=f"Bearer {raw_key}",
            host="new-shared.test",
            origin="https://third-party-client.test",
        )

        self.assertEqual("https://new-shared.test", normalized_url)
        self.assertIsNone(api_domain)
        self.assertEqual(user.id, resolved_user.id)

    def test_database_shared_api_host_cannot_be_used_as_agent_frontend(self):
        config = self.db.query(SystemConfig).filter(SystemConfig.config_key == "api_base_url").first()
        config.config_value = "https://new-shared.test"
        self.db.commit()

        with self.assertRaises(ServiceException) as raised:
            AgentService.update_agent(
                self.db,
                self.agent.id,
                {"frontend_domain": "new-shared.test"},
            )

        self.assertEqual("INVALID_AGENT_FRONTEND_DOMAIN", raised.exception.error_code)

    def test_agent_frontend_domain_wins_over_conflicting_dynamic_shared_host(self):
        import hashlib

        config = self.db.query(SystemConfig).filter(SystemConfig.config_key == "api_base_url").first()
        config.config_value = "https://new-shared.test"
        conflicting_agent = Agent(
            id=8,
            agent_code="agent-8",
            agent_name="Agent 8",
            status="active",
            frontend_domain="new-shared.test",
            allow_self_register=1,
            online_recharge_enabled=1,
            subscription_online_recharge_enabled=1,
            custom_recharge_rate_enabled=0,
            custom_recharge_rate=5,
        )
        user = SysUser(
            id=70,
            username="shared-conflict-user",
            email="shared-conflict-user@example.test",
            password_hash="hash",
            role="user",
            agent_id=self.agent.id,
            status=1,
        )
        raw_key = "sk-shared-conflict-test"
        key = UserApiKey(
            id=71,
            user_id=user.id,
            name="test",
            key_prefix="sk-shared",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            status="active",
        )
        self.db.add_all([conflicting_agent, user, key])
        self.db.commit()

        context = AgentService.get_site_context_from_request(self.db, host="new-shared.test")
        self.assertEqual("agent", context.site_scope)
        self.assertFalse(context.is_api_host)
        self.assertEqual(conflicting_agent.id, context.agent_id)
        with self.assertRaises(ServiceException) as raised:
            verify_api_key_from_headers(
                self.db,
                authorization=f"Bearer {raw_key}",
                host="new-shared.test",
            )
        self.assertEqual("AGENT_DOMAIN_MISMATCH", raised.exception.error_code)

    def test_admin_shared_api_update_rejects_existing_agent_domains(self):
        AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": "https://api.agent.test"},
        )
        config = self.db.query(SystemConfig).filter(SystemConfig.config_key == "api_base_url").first()

        for value in ("https://portal.agent.test", "https://api.agent.test"):
            with self.subTest(value=value), self.assertRaises(ServiceException) as raised:
                update_config(
                    config.id,
                    ConfigUpdate(config_value=value),
                    db=self.db,
                    current_user=SimpleNamespace(id=1),
                )
            self.assertEqual("SHARED_API_DOMAIN_CONFLICT", raised.exception.error_code)

        self.assertEqual("https://api.platform.test", config.config_value)

    def test_agent_api_domain_wins_over_conflicting_dynamic_shared_host(self):
        import hashlib

        AgentService.update_agent(
            self.db,
            self.agent.id,
            {"quickstart_api_base_url": "https://api.agent.test"},
        )
        other_agent = Agent(
            id=8,
            agent_code="agent-8",
            agent_name="Agent 8",
            status="active",
            frontend_domain="portal.agent-8.test",
            allow_self_register=1,
            online_recharge_enabled=1,
            subscription_online_recharge_enabled=1,
            custom_recharge_rate_enabled=0,
            custom_recharge_rate=5,
        )
        user = SysUser(
            id=80,
            username="other-agent-user",
            email="other-agent-user@example.test",
            password_hash="hash",
            role="user",
            agent_id=other_agent.id,
            status=1,
        )
        raw_key = "sk-other-agent-test"
        key = UserApiKey(
            id=81,
            user_id=user.id,
            name="test",
            key_prefix="sk-other",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            status="active",
        )
        config = self.db.query(SystemConfig).filter(SystemConfig.config_key == "api_base_url").first()
        config.config_value = "https://api.agent.test"
        self.db.add_all([other_agent, user, key])
        self.db.commit()

        context = AgentService.get_site_context_from_request(self.db, host="api.agent.test")
        self.assertEqual("agent", context.site_scope)
        self.assertEqual(self.agent.id, context.agent_id)
        with self.assertRaises(ServiceException) as raised:
            verify_api_key_from_headers(
                self.db,
                authorization=f"Bearer {raw_key}",
                host="api.agent.test",
            )
        self.assertEqual("AGENT_DOMAIN_MISMATCH", raised.exception.error_code)

    def test_api_domain_cannot_be_reused_by_another_agent(self):
        self.db.add(Agent(
            id=8,
            agent_code="agent-8",
            agent_name="Agent 8",
            status="active",
            frontend_domain="api.occupied.test",
            allow_self_register=1,
            online_recharge_enabled=1,
            subscription_online_recharge_enabled=1,
            custom_recharge_rate_enabled=0,
            custom_recharge_rate=5,
        ))
        self.db.commit()

        with self.assertRaises(ServiceException) as raised:
            AgentService.update_agent(
                self.db,
                self.agent.id,
                {"quickstart_api_base_url": "https://api.occupied.test"},
            )

        self.assertEqual("DUPLICATE_AGENT_DOMAIN", raised.exception.error_code)


if __name__ == "__main__":
    unittest.main()

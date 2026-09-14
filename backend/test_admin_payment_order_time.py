import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.agent import Agent
from app.models.payment import PaymentRechargeOrder
from app.models.user import SysUser
from app.services.agent_cash_service import AgentCashService


class AdminPaymentOrderTimeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                SysUser.__table__,
                Agent.__table__,
                PaymentRechargeOrder.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(SysUser(id=1, username="tester", email="t@example.com", password_hash="hash", role="user", status=1))

        self.db.add_all([
            self._order(1, "before", datetime(2026, 6, 18, 15, 59, 59)),
            self._order(2, "start", datetime(2026, 6, 18, 16, 0, 0)),
            self._order(3, "inside", datetime(2026, 6, 19, 15, 59, 59)),
            self._order(4, "after", datetime(2026, 6, 19, 16, 0, 0)),
            self._order(5, "subscription", datetime(2026, 6, 19, 10, 0, 0), recharge_type="subscription"),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _order(
        self,
        order_id,
        order_no,
        paid_at,
        recharge_type="balance",
        status="paid",
        payment_channel="alipay",
        amount_cny="1.00",
        credited_usd=None,
        agent_income_cny="0.00",
        created_at=None,
    ):
        usd = credited_usd
        if usd is None:
            usd = "0.000000" if recharge_type == "subscription" else "5.000000"
        return PaymentRechargeOrder(
            id=order_id,
            order_no=order_no,
            payment_channel=payment_channel,
            recharge_type=recharge_type,
            user_id=1,
            amount_cny=Decimal(amount_cny),
            credited_usd=Decimal(usd),
            agent_income_cny=Decimal(agent_income_cny),
            status=status,
            trade_status="TRADE_SUCCESS" if status == "paid" else "WAIT_BUYER_PAY",
            subject="test",
            paid_at=paid_at,
            created_at=created_at or datetime(2026, 6, 19, 12, 0, 0),
            updated_at=datetime(2026, 6, 19, 12, 0, 0),
        )

    def test_paid_at_filter_uses_beijing_day_bounds(self):
        items, total = AgentCashService.list_recharge_orders(
            self.db,
            page=1,
            page_size=20,
            status="paid",
            start_date="2026-06-19",
            end_date="2026-06-19",
            time_field="paid_at",
        )

        self.assertEqual(total, 2)
        self.assertEqual([item["order_no"] for item in items], ["inside", "start"])

    def test_subscription_orders_are_excluded_from_cash_list_by_default(self):
        items, total = AgentCashService.list_recharge_orders(
            self.db,
            page=1,
            page_size=20,
            status="paid",
            start_date="2026-06-19",
            end_date="2026-06-19",
            time_field="paid_at",
        )

        self.assertEqual(total, 2)
        self.assertNotIn("subscription", [item["order_no"] for item in items])

    def test_payment_order_list_can_include_subscription_orders(self):
        items, total = AgentCashService.list_recharge_orders(
            self.db,
            page=1,
            page_size=20,
            status="paid",
            start_date="2026-06-19",
            end_date="2026-06-19",
            time_field="paid_at",
            include_subscription=True,
        )

        self.assertEqual(total, 3)
        self.assertIn("subscription", [item["order_no"] for item in items])

    def test_summary_counts_paid_amount_and_ignores_status_filter(self):
        self.db.add_all([
            self._order(
                10,
                "wechat-paid",
                datetime(2026, 6, 19, 10, 0, 0),
                payment_channel="wechat",
                amount_cny="20.00",
                credited_usd="10.000000",
                agent_income_cny="2.00",
            ),
            self._order(
                11,
                "pending-today",
                None,
                status="pending",
                amount_cny="99.00",
                created_at=datetime(2026, 6, 19, 11, 0, 0),
            ),
        ])
        self.db.commit()

        summary = AgentCashService.summarize_recharge_orders(
            self.db,
            start_date="2026-06-19",
            end_date="2026-06-19",
            time_field="paid_at",
            include_subscription=True,
        )

        self.assertFalse(summary["defaulted_to_today"])
        self.assertEqual(4, summary["paid_count"])
        self.assertEqual(23.0, summary["paid_amount_cny"])
        self.assertEqual(3, summary["alipay_paid_count"])
        self.assertEqual(1, summary["wechat_paid_count"])
        self.assertEqual(20.0, summary["wechat_paid_amount_cny"])
        self.assertEqual(2.0, summary["paid_agent_income_cny"])
        self.assertEqual(0, summary["pending_count"])

        created_summary = AgentCashService.summarize_recharge_orders(
            self.db,
            start_date="2026-06-19",
            end_date="2026-06-19",
            time_field="created_at",
            include_subscription=True,
        )
        self.assertEqual(1, created_summary["pending_count"])
        self.assertEqual(6, created_summary["paid_count"])

    def test_summary_defaults_to_beijing_today_when_no_date(self):
        self.db.add(self._order(
            12,
            "today-paid",
            datetime(2026, 9, 12, 1, 0, 0),
            amount_cny="8.00",
            created_at=datetime(2026, 9, 12, 1, 0, 0),
        ))
        self.db.commit()

        with patch.object(AgentCashService, "_beijing_today", return_value="2026-09-12"):
            summary = AgentCashService.summarize_recharge_orders(
                self.db,
                time_field="created_at",
                include_subscription=True,
            )

        self.assertTrue(summary["defaulted_to_today"])
        self.assertEqual("2026-09-12", summary["range_start"])
        self.assertEqual(1, summary["paid_count"])
        self.assertEqual(8.0, summary["paid_amount_cny"])

    def test_summary_channel_filter_excludes_other_payments(self):
        self.db.add(self._order(
            13,
            "wechat-only",
            datetime(2026, 6, 19, 9, 0, 0),
            payment_channel="wechat",
            amount_cny="30.00",
        ))
        self.db.commit()

        summary = AgentCashService.summarize_recharge_orders(
            self.db,
            payment_channel="wechat",
            start_date="2026-06-19",
            end_date="2026-06-19",
            time_field="paid_at",
            include_subscription=True,
        )
        self.assertEqual(1, summary["paid_count"])
        self.assertEqual(30.0, summary["paid_amount_cny"])
        self.assertEqual(0, summary["alipay_paid_count"])


if __name__ == "__main__":
    unittest.main()

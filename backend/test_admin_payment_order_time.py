import unittest
from datetime import datetime
from decimal import Decimal

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

    def _order(self, order_id, order_no, paid_at, recharge_type="balance"):
        return PaymentRechargeOrder(
            id=order_id,
            order_no=order_no,
            payment_channel="alipay",
            recharge_type=recharge_type,
            user_id=1,
            amount_cny=Decimal("1.00"),
            credited_usd=Decimal("0.000000") if recharge_type == "subscription" else Decimal("5.000000"),
            status="paid",
            trade_status="TRADE_SUCCESS",
            subject="test",
            paid_at=paid_at,
            created_at=datetime(2026, 6, 19, 12, 0, 0),
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


if __name__ == "__main__":
    unittest.main()

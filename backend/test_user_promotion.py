import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ServiceException
from app.database import Base
from app.models.agent import Agent
from app.models.log import ConsumptionRecord, ImageCreditRecord, SystemConfig, UserBalance, UserImageBalance
from app.models.payment import PaymentRechargeOrder
from app.models.promotion import UserPromotionLink, UserPromotionRelation, UserPromotionReward
from app.models.user import SysUser
from app.services.agent_service import AgentSiteContext
from app.services.promotion_service import PromotionService


class UserPromotionTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                SysUser.__table__,
                Agent.__table__,
                UserBalance.__table__,
                UserImageBalance.__table__,
                ConsumptionRecord.__table__,
                ImageCreditRecord.__table__,
                SystemConfig.__table__,
                PaymentRechargeOrder.__table__,
                UserPromotionLink.__table__,
                UserPromotionRelation.__table__,
                UserPromotionReward.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.promoter = SysUser(id=1, username="promoter", email="p@example.com", password_hash="hash", role="user", status=1)
        self.invited = SysUser(id=2, username="invited", email="i@example.com", password_hash="hash", role="user", status=1)
        self.agent_user = SysUser(id=3, username="agent-user", email="a@example.com", password_hash="hash", role="user", agent_id=10, status=1)
        self.manual_invited = SysUser(id=4, username="manual-invited", email="m@example.com", password_hash="hash", role="user", status=1)
        self.db.add_all([
            self.promoter,
            self.invited,
            self.agent_user,
            self.manual_invited,
            UserBalance(id=1, user_id=1, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserBalance(id=2, user_id=2, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserBalance(id=4, user_id=4, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserImageBalance(id=1, user_id=1, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserImageBalance(id=2, user_id=2, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserImageBalance(id=4, user_id=4, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
        ])
        self.db.commit()
        self.now = datetime(2026, 6, 14, 8, 0, 0)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def platform_context(self):
        return AgentSiteContext(host="www.xiaoleai.team", site_scope="platform", is_api_host=False)

    def create_relation(self):
        link = PromotionService.get_or_create_user_link(self.db, self.promoter, self.platform_context())
        PromotionService.bind_invited_user(self.db, self.invited, link.invite_code, self.platform_context())
        self.db.commit()
        return link

    def test_bind_invited_user(self):
        link = self.create_relation()
        relation = self.db.query(UserPromotionRelation).filter(UserPromotionRelation.invited_user_id == 2).first()
        self.assertIsNotNone(relation)
        self.assertEqual(relation.promoter_user_id, 1)
        self.assertEqual(relation.invite_code, link.invite_code)
        self.db.refresh(link)
        self.assertEqual(link.register_count, 1)

    def test_bind_rejects_cross_site_user(self):
        link = PromotionService.get_or_create_user_link(self.db, self.promoter, self.platform_context())
        agent_context = AgentSiteContext(host="agent.xiaoleai.team", site_scope="agent", is_api_host=False, agent=Agent(id=10, agent_code="a", agent_name="A"))
        with self.assertRaises(ServiceException) as ctx:
            PromotionService.bind_invited_user(self.db, self.agent_user, link.invite_code, agent_context)
        self.assertEqual(ctx.exception.error_code, "PROMOTION_SITE_MISMATCH")

    def test_balance_recharge_reward_is_idempotent(self):
        self.create_relation()
        order = PaymentRechargeOrder(
            id=1,
            order_no="ALP202606100001",
            payment_channel="alipay",
            recharge_type="balance",
            user_id=2,
            amount_cny=Decimal("1.00"),
            credited_usd=Decimal("5.000000"),
            credited_image_credits=Decimal("0"),
            status="paid",
            paid_at=self.now,
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.000001")), Decimal("1.000000"))
        self.assertEqual(Decimal(str(balance.total_recharged)).quantize(Decimal("0.000001")), Decimal("0.000000"))
        self.assertEqual(self.db.query(UserPromotionReward).count(), 1)
        relation = self.db.query(UserPromotionRelation).first()
        self.assertIsNotNone(relation.first_recharged_at)
        self.assertEqual(Decimal(str(relation.total_reward_usd)).quantize(Decimal("0.000001")), Decimal("1.000000"))

    def test_image_credit_recharge_reward(self):
        self.create_relation()
        order = PaymentRechargeOrder(
            id=2,
            order_no="ALP202606100002",
            payment_channel="alipay",
            recharge_type="image_credit",
            user_id=2,
            amount_cny=Decimal("2.00"),
            credited_usd=Decimal("0"),
            credited_image_credits=Decimal("10.000"),
            status="paid",
            paid_at=self.now,
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        balance = self.db.query(UserImageBalance).filter(UserImageBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.001")), Decimal("2.000"))
        self.assertEqual(Decimal(str(balance.total_recharged)).quantize(Decimal("0.001")), Decimal("0.000"))
        record = self.db.query(ImageCreditRecord).filter(ImageCreditRecord.user_id == 1).first()
        self.assertEqual(record.action_type, "promotion_reward")

    def test_promotion_reward_rate_config_controls_balance_reward(self):
        self.db.add(SystemConfig(config_key="promotion_reward_rate", config_value="0.1", config_type="number", description="推广返利比例"))
        self.create_relation()
        order = PaymentRechargeOrder(
            id=6,
            order_no="ALP202606100006",
            payment_channel="alipay",
            recharge_type="balance",
            user_id=2,
            amount_cny=Decimal("10.00"),
            credited_usd=Decimal("50.000000"),
            credited_image_credits=Decimal("0"),
            status="paid",
            paid_at=self.now,
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        reward = self.db.query(UserPromotionReward).first()
        self.assertEqual(Decimal(str(reward.reward_rate)).quantize(Decimal("0.000001")), Decimal("0.100000"))
        self.assertEqual(Decimal(str(reward.reward_amount)).quantize(Decimal("0.000001")), Decimal("5.000000"))
        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.000001")), Decimal("5.000000"))

    def test_zero_promotion_reward_rate_disables_reward(self):
        self.db.add(SystemConfig(config_key="promotion_reward_rate", config_value="0", config_type="number", description="推广返利比例"))
        self.create_relation()
        order = PaymentRechargeOrder(
            id=7,
            order_no="ALP202606100007",
            payment_channel="alipay",
            recharge_type="balance",
            user_id=2,
            amount_cny=Decimal("10.00"),
            credited_usd=Decimal("50.000000"),
            credited_image_credits=Decimal("0"),
            status="paid",
            paid_at=self.now,
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        self.assertEqual(self.db.query(UserPromotionReward).count(), 0)
        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.000001")), Decimal("0.000000"))

    def test_manual_bind_relation(self):
        item = PromotionService.manual_bind_relation(self.db, promoter_user_id=1, invited_user_id=4)
        self.assertEqual(item["promoter_user_id"], 1)
        self.assertEqual(item["invited_user_id"], 4)
        relation = self.db.query(UserPromotionRelation).filter(UserPromotionRelation.invited_user_id == 4).first()
        self.assertIsNotNone(relation)
        self.assertEqual(relation.promoter_user_id, 1)
        link = self.db.query(UserPromotionLink).filter(UserPromotionLink.user_id == 1).first()
        self.assertIsNotNone(link)
        self.assertEqual(link.register_count, 1)

    def test_manual_bind_rejects_cross_site_user(self):
        with self.assertRaises(ServiceException) as ctx:
            PromotionService.manual_bind_relation(self.db, promoter_user_id=1, invited_user_id=3)
        self.assertEqual(ctx.exception.error_code, "PROMOTION_SITE_MISMATCH")

    def test_unpaid_order_does_not_reward(self):
        self.create_relation()
        order = PaymentRechargeOrder(
            id=3,
            order_no="ALP202606100003",
            payment_channel="alipay",
            recharge_type="balance",
            user_id=2,
            amount_cny=Decimal("1.00"),
            credited_usd=Decimal("5.000000"),
            credited_image_credits=Decimal("0"),
            status="pending",
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        self.assertEqual(self.db.query(UserPromotionReward).count(), 0)
        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.000001")), Decimal("0.000000"))

    def test_order_created_before_manual_bind_does_not_reward(self):
        order = PaymentRechargeOrder(
            id=4,
            order_no="ALP202606100004",
            payment_channel="alipay",
            recharge_type="balance",
            user_id=4,
            amount_cny=Decimal("1.00"),
            credited_usd=Decimal("5.000000"),
            credited_image_credits=Decimal("0"),
            status="paid",
            paid_at=self.now,
            created_at=self.now,
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.manual_bind_relation(self.db, promoter_user_id=1, invited_user_id=4)
        relation = self.db.query(UserPromotionRelation).filter(UserPromotionRelation.invited_user_id == 4).first()
        order.created_at = relation.created_at - timedelta(seconds=1)
        self.db.commit()
        self.db.refresh(order)
        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        self.assertEqual(self.db.query(UserPromotionReward).count(), 0)
        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.000001")), Decimal("0.000000"))

    def test_order_created_after_manual_bind_rewards(self):
        PromotionService.manual_bind_relation(self.db, promoter_user_id=1, invited_user_id=4)
        relation = self.db.query(UserPromotionRelation).filter(UserPromotionRelation.invited_user_id == 4).first()
        order = PaymentRechargeOrder(
            id=5,
            order_no="ALP202606100005",
            payment_channel="alipay",
            recharge_type="balance",
            user_id=4,
            amount_cny=Decimal("1.00"),
            credited_usd=Decimal("5.000000"),
            credited_image_credits=Decimal("0"),
            status="paid",
            paid_at=self.now + timedelta(seconds=1),
            created_at=relation.created_at + timedelta(seconds=1),
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        self.assertEqual(self.db.query(UserPromotionReward).count(), 1)
        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.000001")), Decimal("1.000000"))


if __name__ == "__main__":
    unittest.main()

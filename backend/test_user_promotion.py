import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ServiceException
from app.database import Base
from app.models.agent import Agent
from app.models.log import ConsumptionRecord, ImageCreditRecord, UserBalance, UserImageBalance
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
        self.db.add_all([
            self.promoter,
            self.invited,
            self.agent_user,
            UserBalance(id=1, user_id=1, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserBalance(id=2, user_id=2, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserImageBalance(id=1, user_id=1, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
            UserImageBalance(id=2, user_id=2, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0")),
        ])
        self.db.commit()

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
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.000001")), Decimal("2.500000"))
        self.assertEqual(Decimal(str(balance.total_recharged)).quantize(Decimal("0.000001")), Decimal("0.000000"))
        self.assertEqual(self.db.query(UserPromotionReward).count(), 1)
        relation = self.db.query(UserPromotionRelation).first()
        self.assertIsNotNone(relation.first_recharged_at)
        self.assertEqual(Decimal(str(relation.total_reward_usd)).quantize(Decimal("0.000001")), Decimal("2.500000"))

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
            subject="充值",
        )
        self.db.add(order)
        self.db.commit()

        PromotionService.apply_recharge_reward(self.db, order)
        self.db.commit()

        balance = self.db.query(UserImageBalance).filter(UserImageBalance.user_id == 1).first()
        self.assertEqual(Decimal(str(balance.balance)).quantize(Decimal("0.001")), Decimal("5.000"))
        self.assertEqual(Decimal(str(balance.total_recharged)).quantize(Decimal("0.001")), Decimal("0.000"))
        record = self.db.query(ImageCreditRecord).filter(ImageCreditRecord.user_id == 1).first()
        self.assertEqual(record.action_type, "promotion_reward")


if __name__ == "__main__":
    unittest.main()

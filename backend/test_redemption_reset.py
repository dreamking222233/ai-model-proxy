import unittest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ServiceException
from app.database import Base
from app.models.log import UserBalance
from app.models.redemption import RedemptionCode
from app.models.user import SysUser
from app.services.redemption_service import RedemptionService


class RedemptionResetTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                SysUser.__table__,
                UserBalance.__table__,
                RedemptionCode.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.user = SysUser(
            id=1,
            username="redeem-user",
            email="redeem@example.com",
            password_hash="hash",
            role="user",
            redemption_reset_count=0,
        )
        self.balance = UserBalance(
            id=1,
            user_id=1,
            balance=Decimal("0"),
            total_recharged=Decimal("0"),
            total_consumed=Decimal("0"),
        )
        self.used_code = RedemptionCode(
            id=1,
            code="USED-CODE-001",
            amount=Decimal("5.000000"),
            status="used",
            created_by=999,
            used_by=1,
            used_at=datetime.now(),
        )
        self.unused_code = RedemptionCode(
            id=2,
            code="UNUSED-CODE-002",
            amount=Decimal("7.500000"),
            status="unused",
            created_by=999,
        )
        self.db.add_all([self.user, self.balance, self.used_code, self.unused_code])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_reset_allows_user_to_redeem_new_code(self):
        info = RedemptionService.get_user_redemption_info(self.db, 1)
        self.assertTrue(info["has_redeemed"])
        self.assertEqual(info["redeemed_count"], 1)
        self.assertEqual(info["allowed_redeem_count"], 1)
        self.assertEqual(info["remaining_redeem_count"], 0)

        with self.assertRaises(ServiceException) as ctx:
            RedemptionService.redeem_code(self.db, 1, "UNUSED-CODE-002")
        self.assertEqual(ctx.exception.error_code, "USER_ALREADY_REDEEMED")

        reset_result = RedemptionService.reset_user_redemption_quota(self.db, 1)
        self.assertEqual(reset_result["redemption_reset_count"], 1)
        self.assertEqual(reset_result["allowed_redeem_count"], 2)
        self.assertEqual(reset_result["remaining_redeem_count"], 1)

        refreshed_info = RedemptionService.get_user_redemption_info(self.db, 1)
        self.assertFalse(refreshed_info["has_redeemed"])
        self.assertEqual(refreshed_info["remaining_redeem_count"], 1)

        result = RedemptionService.redeem_code(self.db, 1, "UNUSED-CODE-002")
        self.assertEqual(result["amount"], 7.5)
        self.assertEqual(result["redeemed_count"], 2)
        self.assertEqual(result["allowed_redeem_count"], 2)
        self.assertEqual(result["remaining_redeem_count"], 0)

        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 1).first()
        self.assertEqual(float(balance.balance), 7.5)


if __name__ == "__main__":
    unittest.main()

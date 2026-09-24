import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.model import ModelCategory, ModelPriceAdjustmentRule, UnifiedModel
from app.services.price_adjustment_service import PriceAdjustmentService


class ModelCategoryPricingTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[ModelCategory.__table__, UnifiedModel.__table__, ModelPriceAdjustmentRule.__table__],
        )
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_category_rule_precedes_series_rule(self):
        self.db.add_all([
            ModelCategory(id=1, code="claude", name="Claude", model_series="claude", enabled=1),
            ModelCategory(id=2, code="claude-cc", name="Claude Code", model_series="claude", enabled=1),
            UnifiedModel(
                id=1,
                model_name="claude-opus-max",
                model_series="claude",
                model_category="claude-cc",
                model_type="chat",
                billing_type="token",
            ),
            ModelPriceAdjustmentRule(
                id=1,
                name="Claude series",
                model_series="claude",
                model_category="all",
                model_type="chat",
                billing_type="token",
                multiplier=Decimal("1.2"),
                enabled=1,
                priority=1,
            ),
            ModelPriceAdjustmentRule(
                id=2,
                name="Claude Code category",
                model_series="claude",
                model_category="claude-cc",
                model_type="chat",
                billing_type="token",
                multiplier=Decimal("2.5"),
                enabled=1,
                priority=100,
            ),
        ])
        self.db.commit()

        resolution = PriceAdjustmentService.resolve_adjustment(self.db, self.db.get(UnifiedModel, 1))

        self.assertEqual(resolution.multiplier, Decimal("2.500000"))
        self.assertEqual(resolution.rule_name, "Claude Code category")

    def test_category_must_belong_to_model_series(self):
        from app.core.exceptions import ServiceException
        from app.services.model_category_service import ModelCategoryService

        self.db.add(ModelCategory(id=1, code="gpt-max", name="GPT Max", model_series="gpt", enabled=1))
        self.db.commit()
        with self.assertRaises(ServiceException):
            ModelCategoryService.validate_for_model(self.db, "gpt-max", "claude")


if __name__ == "__main__":
    unittest.main()

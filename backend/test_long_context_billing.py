import unittest
from decimal import Decimal
from unittest.mock import patch

from pydantic import ValidationError

from app.core.exceptions import ServiceException
from app.models.model import ModelImageResolutionRule, UnifiedModel
from app.schemas.model import UnifiedModelCreate, UnifiedModelUpdate
from app.services.model_service import ModelService
from app.services.price_adjustment_service import PriceAdjustmentResolution
from app.services.proxy_service import ProxyService


class FakeDb:
    pass


class FakeQuery:
    def __init__(self, first_result=None):
        self.first_result = first_result

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_result

    def all(self):
        return []


class FakeModelDb:
    def __init__(self, existing_model=None):
        self.existing_model = existing_model
        self.added_model = None

    def query(self, entity):
        if entity is UnifiedModel:
            return FakeQuery(self.existing_model)
        if entity is ModelImageResolutionRule:
            return FakeQuery()
        return FakeQuery()

    def add(self, model):
        self.added_model = model

    def flush(self):
        if self.added_model is not None and self.added_model.id is None:
            self.added_model.id = 1

    def commit(self):
        pass

    def refresh(self, model):
        pass


class LongContextBillingTest(unittest.TestCase):
    def test_context_multiplier_respects_model_switch(self):
        enabled_model = UnifiedModel(
            model_name="gpt-test",
            long_context_billing_enabled=1,
            long_context_token_threshold=200000,
        )
        disabled_model = UnifiedModel(model_name="claude-test", long_context_billing_enabled=0)

        self.assertEqual(
            ProxyService._get_context_price_multiplier_decimal(200000, enabled_model),
            Decimal("1"),
        )
        self.assertEqual(
            ProxyService._get_context_price_multiplier_decimal(200001, enabled_model),
            Decimal("2"),
        )
        self.assertEqual(
            ProxyService._get_context_price_multiplier_decimal(300000, disabled_model),
            Decimal("1"),
        )

    def test_threshold_defaults_and_validation(self):
        self.assertEqual(
            ModelService._normalize_long_context_token_threshold(None),
            ProxyService._LONG_CONTEXT_TOKEN_THRESHOLD,
        )
        self.assertEqual(ModelService._normalize_long_context_token_threshold("200000"), 200000)
        for invalid_value in (0, -1, "1.5", "invalid", 2147483648):
            with self.subTest(value=invalid_value), self.assertRaises(ServiceException):
                ModelService._normalize_long_context_token_threshold(invalid_value)

    def test_model_schema_exposes_configurable_threshold(self):
        create = UnifiedModelCreate(model_name="gpt-threshold")
        update = UnifiedModelUpdate(long_context_token_threshold=200000)

        self.assertIsNone(create.long_context_token_threshold)
        self.assertEqual(update.model_dump(exclude_unset=True)["long_context_token_threshold"], 200000)

    def test_model_schema_rejects_unsafe_explicit_threshold_values(self):
        for invalid_value in (None, True, False, 0, 1.5, 2147483648):
            with self.subTest(schema="create", value=invalid_value), self.assertRaises(ValidationError):
                UnifiedModelCreate(
                    model_name="gpt-invalid-threshold",
                    long_context_token_threshold=invalid_value,
                )
            with self.subTest(schema="update", value=invalid_value), self.assertRaises(ValidationError):
                UnifiedModelUpdate(long_context_token_threshold=invalid_value)

    def test_model_service_create_and_update_preserve_threshold(self):
        create_db = FakeModelDb()
        created = ModelService.create_model(
            create_db,
            UnifiedModelCreate(model_name="gpt-default-threshold"),
        )
        self.assertEqual(created["long_context_token_threshold"], 262144)
        self.assertEqual(create_db.added_model.long_context_token_threshold, 262144)

        existing_model = UnifiedModel(
            id=2,
            model_name="gpt-custom-threshold",
            display_name="before",
            model_type="chat",
            model_series="gpt",
            protocol_type="openai",
            billing_type="token",
            long_context_billing_enabled=1,
            long_context_token_threshold=200000,
        )
        updated = ModelService.update_model(
            FakeModelDb(existing_model),
            existing_model.id,
            UnifiedModelUpdate(display_name="after"),
        )
        self.assertEqual(updated["long_context_token_threshold"], 200000)
        self.assertEqual(existing_model.long_context_token_threshold, 200000)
        with self.assertRaises(ServiceException):
            ModelService.update_model(
                FakeModelDb(existing_model),
                existing_model.id,
                {"long_context_token_threshold": None},
            )

    def test_gpt_defaults_to_long_context_billing_enabled(self):
        self.assertEqual(
            ModelService._normalize_long_context_billing_enabled(None, "gpt", "gpt-test"),
            1,
        )
        self.assertEqual(
            ModelService._normalize_long_context_billing_enabled(None, "claude", "claude-test"),
            0,
        )

    def test_request_precheck_respects_disabled_model_switch_without_output_limit(self):
        model = UnifiedModel(
            model_name="claude-request",
            model_type="chat",
            model_series="claude",
            billing_type="request",
            request_price=Decimal("0.25"),
            long_context_billing_enabled=0,
            long_context_token_threshold=200000,
        )
        request_data = {
            "model": "claude-request",
            "messages": [{"role": "user", "content": "hello"}],
        }

        with (
            patch("app.services.proxy_service.get_system_config", return_value=1),
            patch(
                "app.services.proxy_service.PriceAdjustmentService.resolve_adjustment",
                return_value=PriceAdjustmentResolution(multiplier=Decimal("1")),
            ),
        ):
            precheck = ProxyService._build_text_quota_precheck(
                FakeDb(),
                "openai",
                request_data,
                model,
            )

        self.assertEqual(precheck["context_price_multiplier_snapshot"], Decimal("1"))
        self.assertEqual(precheck["context_token_threshold_snapshot"], Decimal("200000"))
        self.assertEqual(precheck["estimated_total_cost"], Decimal("0.25"))

    def test_request_precheck_keeps_conservative_multiplier_when_model_switch_enabled(self):
        model = UnifiedModel(
            model_name="gpt-request",
            model_type="chat",
            model_series="gpt",
            billing_type="request",
            request_price=Decimal("0.25"),
            long_context_billing_enabled=1,
            long_context_token_threshold=200000,
        )
        request_data = {
            "model": "gpt-request",
            "messages": [{"role": "user", "content": "hello"}],
        }

        with (
            patch("app.services.proxy_service.get_system_config", return_value=1),
            patch(
                "app.services.proxy_service.PriceAdjustmentService.resolve_adjustment",
                return_value=PriceAdjustmentResolution(multiplier=Decimal("1")),
            ),
        ):
            precheck = ProxyService._build_text_quota_precheck(
                FakeDb(),
                "openai",
                request_data,
                model,
            )

        self.assertEqual(precheck["context_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(precheck["context_token_threshold_snapshot"], Decimal("200000"))
        self.assertEqual(precheck["context_tokens_snapshot"], Decimal("200001"))
        self.assertEqual(precheck["estimated_total_cost"], Decimal("0.50"))

    def test_token_precheck_uses_custom_threshold_for_cost_and_quota(self):
        model = UnifiedModel(
            model_name="gpt-token-threshold",
            model_type="chat",
            model_series="gpt",
            billing_type="token",
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("0"),
            long_context_billing_enabled=1,
            long_context_token_threshold=200000,
        )

        with (
            patch("app.services.proxy_service.ProxyService.estimate_openai_input_tokens", return_value=200001),
            patch("app.services.proxy_service.get_system_config", return_value=1),
            patch(
                "app.services.proxy_service.PriceAdjustmentService.resolve_adjustment",
                return_value=PriceAdjustmentResolution(multiplier=Decimal("1")),
            ),
        ):
            precheck = ProxyService._build_text_quota_precheck(
                FakeDb(),
                "openai",
                {"model": "gpt-token-threshold", "messages": []},
                model,
            )

        self.assertEqual(precheck["context_token_threshold_snapshot"], Decimal("200000"))
        self.assertEqual(precheck["context_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(precheck["estimated_total_cost"], Decimal("0.400002"))
        self.assertEqual(precheck["estimated_quota_cost"], Decimal("0.400002"))

        # The existing mixed-billing helper must carry the threshold-adjusted cost
        # into full and proportional balance charges after package quota is exhausted.
        self.assertEqual(
            ProxyService._calculate_balance_charge_after_quota(
                precheck["estimated_total_cost"],
                precheck["estimated_quota_cost"],
                Decimal("0"),
            ),
            Decimal("0.400002"),
        )
        self.assertEqual(
            ProxyService._calculate_balance_charge_after_quota(
                precheck["estimated_total_cost"],
                precheck["estimated_quota_cost"],
                Decimal("0.200001"),
            ),
            Decimal("0.2000010"),
        )


if __name__ == "__main__":
    unittest.main()

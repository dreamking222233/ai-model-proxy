import unittest
from decimal import Decimal
from types import SimpleNamespace

from app.services.model_service import ModelService


class ModelAdminSerializationTest(unittest.TestCase):
    def test_model_to_dict_exposes_image_capabilities_and_edit_support(self):
        payload = ModelService._model_to_dict(
            SimpleNamespace(
                id=1,
                model_name="gpt-image-2",
                display_name="GPT Image 2",
                model_type="image",
                protocol_type="openai",
                max_tokens=0,
                input_price_per_million=Decimal("0"),
                output_price_per_million=Decimal("0"),
                billing_type="image_credit",
                image_credit_multiplier=Decimal("0.500"),
                enabled=1,
                description=None,
                created_at=None,
                updated_at=None,
            )
        )

        self.assertEqual(payload["image_size_capabilities"], ["512", "1K", "2K", "4K"])
        self.assertTrue(payload["supports_image_edit"])

    def test_mapping_with_channel_to_dict_exposes_openai_image_channel_capabilities(self):
        payload = ModelService._mapping_with_channel_to_dict(
            SimpleNamespace(
                id=11,
                unified_model_id=1,
                channel_id=2,
                actual_model_name="gpt-image-2",
                enabled=1,
                created_at=None,
            ),
            SimpleNamespace(
                id=2,
                name="Native Size",
                protocol_type="openai",
                provider_variant="openai-image-native-size",
            ),
        )

        self.assertEqual(payload["channel_provider_variant"], "openai-image-native-size")
        self.assertEqual(payload["supported_image_sizes"], ["1K", "2K", "4K"])
        self.assertTrue(payload["supports_image_edit"])


if __name__ == "__main__":
    unittest.main()

import unittest

from app.services.model_service import ModelService


class GrokTextCompatibilityTest(unittest.TestCase):
    def test_grok_series_models_are_inferred_as_grok(self):
        samples = [
            "grok-composer-2.5-fast",
            "grok-imagine-image",
            "grok-4.3",
            "grok-4.20-0309-reasoning",
            "grok-4.20-0309-non-reasoning",
            "grok-4.20-multi-agent-0309",
            "grok-imagine-image-quality",
            "grok-imagine-video",
            "grok-imagine-video-1.5-preview",
            "grok-build-0.1",
            "grok-3-mini",
            "grok-3-mini-fast",
        ]

        for model_name in samples:
            with self.subTest(model_name=model_name):
                self.assertEqual(ModelService.infer_model_series(model_name), "grok")

    def test_grok_models_can_be_configured_as_openai_protocol_channels(self):
        self.assertIn("grok", ModelService.MODEL_SERIES_VALUES)
        self.assertEqual(ModelService.normalize_model_series("grok", "grok-4.3"), "grok")

    def test_security_monitor_defaults_follow_model_series(self):
        self.assertEqual(ModelService._normalize_security_monitor_enabled(None, "gpt", "gpt-4o"), 1)
        self.assertEqual(ModelService._normalize_security_monitor_enabled(None, "claude", "claude-opus-4"), 1)
        self.assertEqual(ModelService._normalize_security_monitor_enabled(None, "grok", "grok-4.3"), 0)
        self.assertEqual(ModelService._normalize_security_monitor_enabled(None, "gemini", "gemini-2.5-pro"), 0)


if __name__ == "__main__":
    unittest.main()

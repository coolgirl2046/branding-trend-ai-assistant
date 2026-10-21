import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.config import (
    ConfigurationError,
    load_ai_settings,
)


MISSING_ENV_FILE = Path(__file__).with_name("missing-ai-test.env")


class AIConfigTests(unittest.TestCase):
    def load_settings(self, environment):
        with patch.dict(os.environ, environment, clear=True):
            return load_ai_settings(MISSING_ENV_FILE)

    def test_openai_is_the_default_provider(self):
        settings = self.load_settings(
            {
                "OPENAI_API_KEY": "openai-test-key",
                "OPENAI_BASE_URL": "https://openai.example/v1",
                "OPENAI_MODEL": "openai-test-model",
            }
        )

        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.api_key, "openai-test-key")
        self.assertEqual(settings.base_url, "https://openai.example/v1")
        self.assertEqual(settings.model, "openai-test-model")

    def test_explicit_openai_does_not_require_gemini_settings(self):
        settings = self.load_settings(
            {
                "AI_PROVIDER": "openai",
                "OPENAI_API_KEY": "openai-test-key",
                "OPENAI_BASE_URL": "https://openai.example/v1",
                "OPENAI_MODEL": "openai-test-model",
            }
        )

        self.assertEqual(settings.provider, "openai")

    def test_gemini_does_not_require_openai_settings(self):
        settings = self.load_settings(
            {
                "AI_PROVIDER": "gemini",
                "GEMINI_API_KEY": "gemini-test-key",
                "GEMINI_BASE_URL": "https://gemini.example/openai/",
                "GEMINI_MODEL": "gemini-test-model",
            }
        )

        self.assertEqual(settings.provider, "gemini")
        self.assertEqual(settings.api_key, "gemini-test-key")
        self.assertEqual(settings.base_url, "https://gemini.example/openai/")
        self.assertEqual(settings.model, "gemini-test-model")

    def test_invalid_provider_is_rejected(self):
        with self.assertRaises(ConfigurationError) as raised:
            self.load_settings({"AI_PROVIDER": "unsupported"})

        self.assertIn("openai 또는 gemini", str(raised.exception))

    def test_missing_selected_provider_setting_is_rejected(self):
        with self.assertRaises(ConfigurationError) as raised:
            self.load_settings(
                {
                    "AI_PROVIDER": "gemini",
                    "GEMINI_BASE_URL": "https://gemini.example/openai/",
                    "GEMINI_MODEL": "gemini-test-model",
                }
            )

        message = str(raised.exception)
        self.assertIn("GEMINI_API_KEY", message)
        self.assertNotIn("OPENAI_API_KEY", message)

    def test_api_key_is_not_exposed_by_repr(self):
        secret = "DO_NOT_EXPOSE_AI_KEY"
        settings = self.load_settings(
            {
                "AI_PROVIDER": "openai",
                "OPENAI_API_KEY": secret,
                "OPENAI_BASE_URL": "https://openai.example/v1",
                "OPENAI_MODEL": "openai-test-model",
            }
        )

        self.assertNotIn(secret, repr(settings))


if __name__ == "__main__":
    unittest.main()


class TokenLimitTests(unittest.TestCase):
    def test_invalid_limits_and_parameter_are_rejected(self):
        base = {"OPENAI_API_KEY": "test", "OPENAI_BASE_URL": "https://example.com/v1", "OPENAI_MODEL": "test"}
        for extra in [{"AI_MAX_OUTPUT_TOKENS": "0"}, {"AI_MAX_OUTPUT_TOKENS": "4097"}, {"AI_MAX_OUTPUT_TOKENS": "abc"}, {"AI_TOKEN_PARAMETER": "invalid"}]:
            with self.subTest(extra=extra), patch.dict(os.environ, base | extra, clear=True):
                with self.assertRaises(ConfigurationError):
                    load_ai_settings(MISSING_ENV_FILE)

    def test_default_limit_and_compatibility_parameter(self):
        base = {"OPENAI_API_KEY": "test", "OPENAI_BASE_URL": "https://example.com/v1", "OPENAI_MODEL": "test"}
        with patch.dict(os.environ, base, clear=True):
            self.assertEqual(load_ai_settings(MISSING_ENV_FILE).max_output_tokens, 800)
        with patch.dict(os.environ, base | {"AI_TOKEN_PARAMETER": "max_tokens", "AI_MAX_OUTPUT_TOKENS": "256"}, clear=True):
            settings = load_ai_settings(MISSING_ENV_FILE)
            self.assertEqual((settings.token_parameter, settings.max_output_tokens), ("max_tokens", 256))

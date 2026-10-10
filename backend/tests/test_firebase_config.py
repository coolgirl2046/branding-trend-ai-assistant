import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.config import (
    ConfigurationError,
    FirebaseSettings,
    load_firebase_settings,
)
from backend.app.database import (
    FirebaseInitializationError,
    _create_firebase_credential,
)


PROJECT_ID = "branding-trend-ai-assistant"
ENV_FILE_THAT_DOES_NOT_EXIST = Path("missing-test.env")


def service_account_payload():
    return {
        "type": "service_account",
        "project_id": PROJECT_ID,
        "private_key": "test-private-key-value",
        "client_email": "test-service-account@example.invalid",
    }


class FirebaseConfigTests(unittest.TestCase):
    def load_settings(self, environment):
        with patch.dict(os.environ, environment, clear=True):
            return load_firebase_settings(ENV_FILE_THAT_DOES_NOT_EXIST)

    def test_json_body_credential_is_supported(self):
        settings = self.load_settings(
            {
                "FIREBASE_PROJECT_ID": PROJECT_ID,
                "FIREBASE_SERVICE_ACCOUNT_JSON": json.dumps(
                    service_account_payload()
                ),
            }
        )
        fake_certificate = SimpleNamespace(project_id=PROJECT_ID)

        with patch(
            "backend.app.database.credentials.Certificate",
            return_value=fake_certificate,
        ) as certificate_factory:
            result = _create_firebase_credential(settings)

        self.assertIs(result, fake_certificate)
        self.assertIsInstance(certificate_factory.call_args.args[0], dict)

    def test_file_path_credential_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            credential_path = Path(temporary_directory) / "service-account.json"
            credential_path.write_text("{}", encoding="utf-8")
            settings = self.load_settings(
                {
                    "FIREBASE_PROJECT_ID": PROJECT_ID,
                    "FIREBASE_SERVICE_ACCOUNT_PATH": str(credential_path),
                }
            )
            fake_certificate = SimpleNamespace(project_id=PROJECT_ID)

            with patch(
                "backend.app.database.credentials.Certificate",
                return_value=fake_certificate,
            ) as certificate_factory:
                result = _create_firebase_credential(settings)

        self.assertIs(result, fake_certificate)
        certificate_factory.assert_called_once_with(str(credential_path))

    def test_json_body_takes_precedence_when_both_are_set(self):
        settings = self.load_settings(
            {
                "FIREBASE_PROJECT_ID": PROJECT_ID,
                "FIREBASE_SERVICE_ACCOUNT_JSON": json.dumps(
                    service_account_payload()
                ),
                "FIREBASE_SERVICE_ACCOUNT_PATH": "path-that-must-not-be-used.json",
            }
        )
        fake_certificate = SimpleNamespace(project_id=PROJECT_ID)

        with patch(
            "backend.app.database.credentials.Certificate",
            return_value=fake_certificate,
        ) as certificate_factory:
            _create_firebase_credential(settings)

        self.assertIsInstance(certificate_factory.call_args.args[0], dict)

    def test_missing_json_and_path_raise_configuration_error(self):
        with self.assertRaises(ConfigurationError) as raised:
            self.load_settings({"FIREBASE_PROJECT_ID": PROJECT_ID})

        message = str(raised.exception)
        self.assertIn("FIREBASE_SERVICE_ACCOUNT_JSON", message)
        self.assertIn("FIREBASE_SERVICE_ACCOUNT_PATH", message)

    def test_nonexistent_path_raises_safe_error(self):
        nonexistent_path = "C:/sensitive/location/missing-service-account.json"
        settings = FirebaseSettings(
            project_id=PROJECT_ID,
            service_account_path=nonexistent_path,
        )

        with self.assertRaises(FirebaseInitializationError) as raised:
            _create_firebase_credential(settings)

        self.assertNotIn(nonexistent_path, str(raised.exception))
        self.assertIn("유효한 파일", str(raised.exception))

    def test_sensitive_values_are_hidden_from_repr_and_errors(self):
        private_key = "private-key-that-must-not-appear"
        client_email = "secret-account@example.invalid"
        payload = service_account_payload()
        payload["private_key"] = private_key
        payload["client_email"] = client_email
        raw_json = json.dumps(payload)
        settings = FirebaseSettings(
            project_id=PROJECT_ID,
            service_account_json=raw_json,
            service_account_path="C:/also-sensitive/service-account.json",
        )

        with patch(
            "backend.app.database.credentials.Certificate",
            side_effect=ValueError(f"{private_key} {client_email}"),
        ):
            with self.assertRaises(FirebaseInitializationError) as raised:
                _create_firebase_credential(settings)

        combined_output = repr(settings) + str(raised.exception)
        self.assertNotIn(private_key, combined_output)
        self.assertNotIn(client_email, combined_output)
        self.assertNotIn(raw_json, combined_output)
        self.assertNotIn(settings.service_account_path, combined_output)


if __name__ == "__main__":
    unittest.main()

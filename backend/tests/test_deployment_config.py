import os
import unittest
from unittest.mock import patch

from backend.app.main import (
    APPLICATION_INFO_LOGGERS,
    LOCAL_ORIGINS,
    _allowed_origins,
    _uvicorn_logging_config,
)


class DeploymentConfigTests(unittest.TestCase):
    def test_application_info_loggers_use_uvicorn_default_handler(self):
        config = _uvicorn_logging_config()

        self.assertFalse(config["disable_existing_loggers"])
        self.assertEqual(config["loggers"]["uvicorn"]["level"], "INFO")
        self.assertIn("default", config["loggers"]["uvicorn"]["handlers"])
        self.assertEqual(config["loggers"]["uvicorn.error"]["level"], "INFO")
        self.assertIn("access", config["loggers"]["uvicorn.access"]["handlers"])
        for logger_name in APPLICATION_INFO_LOGGERS:
            self.assertEqual(
                config["loggers"][logger_name],
                {
                    "handlers": ["default"],
                    "level": "INFO",
                    "propagate": False,
                },
            )

    def test_local_origins_are_used_when_environment_is_empty(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=True):
            self.assertEqual(_allowed_origins(), list(LOCAL_ORIGINS))

    def test_environment_origins_are_split_and_normalized(self):
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": " https://site.example/ , https://preview.example "},
            clear=True,
        ):
            self.assertEqual(
                _allowed_origins(),
                ["https://site.example", "https://preview.example"],
            )


if __name__ == "__main__":
    unittest.main()

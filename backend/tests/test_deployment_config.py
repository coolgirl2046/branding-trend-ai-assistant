import os
import unittest
from unittest.mock import patch

from backend.app.main import LOCAL_ORIGINS, _allowed_origins


class DeploymentConfigTests(unittest.TestCase):
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

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import config_manager


class ConfigManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "api_keys.json"
        self.env_patch = patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_gemini_key_prefers_environment_variable(self) -> None:
        os.environ["GEMINI_API_KEY"] = "env-gemini-key"
        self.config_path.write_text('{"gemini_api_key": "file-gemini-key"}', encoding="utf-8")

        with patch.object(config_manager, "CONFIG_FILE", self.config_path):
            self.assertEqual(config_manager.get_gemini_key(), "env-gemini-key")


if __name__ == "__main__":
    unittest.main()

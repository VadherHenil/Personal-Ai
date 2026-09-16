import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import memory_manager


class MemoryManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.memory_path = Path(self.temp_dir.name) / "long_term.json"

    def test_update_memory_creates_expected_structure(self) -> None:
        with patch.object(memory_manager, "MEMORY_PATH", self.memory_path):
            memory = memory_manager.update_memory({"identity": {"name": {"value": "Ada"}}})
            self.assertEqual(memory["identity"]["name"]["value"], "Ada")
            self.assertIn("identity", memory)

    def test_forget_returns_not_found_for_missing_key(self) -> None:
        with patch.object(memory_manager, "MEMORY_PATH", self.memory_path):
            self.assertEqual(memory_manager.forget("missing"), "Not found: notes/missing")


if __name__ == "__main__":
    unittest.main()

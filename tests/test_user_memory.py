import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import user_memory


class UserMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "memory.sqlite3"

    def test_reflection_distills_and_deduplicates_explicit_facts(self) -> None:
        with patch.object(user_memory, "MEMORY_DB_PATH", self.db_path):
            first = user_memory.reflect_on_turn("user-a", "I prefer concise answers.", "session-1")
            second = user_memory.reflect_on_turn("user-a", "I prefer concise answers.", "session-1")
            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 1)
            self.assertEqual(len(user_memory.list_memories("user-a")), 1)
            self.assertIn("concise answers", user_memory.format_memories_for_prompt("user-a"))

    def test_memory_isolation_and_sensitive_redaction(self) -> None:
        with patch.object(user_memory, "MEMORY_DB_PATH", self.db_path):
            item = user_memory.upsert_memory("user-a", "TECH_STACK", "Uses user@example.com")
            self.assertNotIn("user@example.com", item["fact"])
            self.assertEqual(user_memory.list_memories("user-b"), [])
            self.assertFalse(user_memory.delete_memory("user-b", item["id"]))
            self.assertTrue(user_memory.delete_memory("user-a", item["id"]))


if __name__ == "__main__":
    unittest.main()

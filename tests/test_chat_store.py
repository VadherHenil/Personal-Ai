import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import chat_store


class ChatStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "chat.sqlite3"

    def test_session_messages_and_ownership(self) -> None:
        with patch.object(chat_store, "CHAT_DB_PATH", self.db_path):
            session_id = chat_store.create_session("user-a", "Build notes")
            message_id = chat_store.append_message(session_id, "user-a", "user", "hello")
            chat_store.append_message(session_id, "user-a", "assistant", "hi")
            session = chat_store.get_session(session_id, "user-a")
            self.assertEqual(session["title"], "Build notes")
            self.assertEqual(len(session["messages"]), 2)
            self.assertEqual(session["messages"][0]["id"], message_id)
            self.assertIsNone(chat_store.get_session(session_id, "user-b"))
            with self.assertRaises(PermissionError):
                chat_store.append_message(session_id, "user-b", "user", "intrude")

    def test_branch_copies_only_through_selected_message(self) -> None:
        with patch.object(chat_store, "CHAT_DB_PATH", self.db_path):
            source = chat_store.create_session("user-a")
            first = chat_store.append_message(source, "user-a", "user", "one")
            chat_store.append_message(source, "user-a", "assistant", "two")
            chat_store.append_message(source, "user-a", "user", "three")
            branch = chat_store.branch_session(source, first, "user-a")
            messages = chat_store.get_session(branch, "user-a")["messages"]
            self.assertEqual([item["content"] for item in messages], ["one"])
            self.assertNotEqual(messages[0]["id"], first)

    def test_edit_truncates_later_continuation(self) -> None:
        with patch.object(chat_store, "CHAT_DB_PATH", self.db_path):
            session = chat_store.create_session("user-a")
            prompt = chat_store.append_message(session, "user-a", "user", "original")
            chat_store.append_message(session, "user-a", "assistant", "old answer")
            chat_store.append_message(session, "user-a", "user", "later prompt")
            self.assertTrue(chat_store.update_message(prompt, "user-a", "revised"))
            messages = chat_store.get_session(session, "user-a")["messages"]
            self.assertEqual([item["content"] for item in messages], ["revised"])

    def test_fork_is_independent(self) -> None:
        with patch.object(chat_store, "CHAT_DB_PATH", self.db_path):
            source = chat_store.create_session("user-a", "Source")
            chat_store.append_message(source, "user-a", "user", "hello")
            fork = chat_store.fork_session(source, "user-a")
            chat_store.append_message(fork, "user-a", "user", "fork only")
            self.assertEqual(len(chat_store.get_session(source, "user-a")["messages"]), 1)
            self.assertEqual(chat_store.get_session(fork, "user-a")["title"], "Fork of Source")


if __name__ == "__main__":
    unittest.main()

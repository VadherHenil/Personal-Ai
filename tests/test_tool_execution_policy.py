import unittest

from security.controls import validate_runtime_tool_call
from tool_registry import get_enabled_tool_declarations


class ToolExecutionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.declarations = get_enabled_tool_declarations()

    def test_disabled_plugin_is_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            validate_runtime_tool_call(
                "web_search", {"query": "python"}, self.declarations,
                enabled_plugins={"web_search": False}, permissions={},
            )

    def test_capability_permission_is_required(self) -> None:
        with self.assertRaises(PermissionError):
            validate_runtime_tool_call(
                "file_controller", {"action": "list"}, self.declarations,
                enabled_plugins={"file_controller": True}, permissions={"files": False},
            )

    def test_destructive_action_still_requires_approval(self) -> None:
        with self.assertRaises(PermissionError):
            validate_runtime_tool_call(
                "file_controller", {"action": "delete", "path": "x"}, self.declarations,
                enabled_plugins={"file_controller": True}, permissions={"files": True},
            )


if __name__ == "__main__":
    unittest.main()

import asyncio
import unittest

from core.tool_queue import ToolExecutionQueue


class ToolQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_executes_and_returns_result(self) -> None:
        queue = ToolExecutionQueue(workers=1, maxsize=2)

        async def work(value: int) -> int:
            await asyncio.sleep(0)
            return value * 2

        try:
            self.assertEqual(await queue.submit(work, 21), 42)
        finally:
            await queue.close()


if __name__ == "__main__":
    unittest.main()

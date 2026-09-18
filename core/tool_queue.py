"""Bounded async execution queue for model tools."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class ToolExecutionQueue:
    def __init__(self, workers: int = 2, maxsize: int = 32):
        self._queue: asyncio.Queue[tuple[Callable[..., Awaitable[Any]], tuple, dict, asyncio.Future]] = asyncio.Queue(maxsize=maxsize)
        self._workers = max(1, int(workers))
        self._tasks: list[asyncio.Task] = []
        self._started = False

    def _ensure_started(self) -> None:
        if not self._started:
            self._tasks = [asyncio.create_task(self._worker()) for _ in range(self._workers)]
            self._started = True

    async def submit(self, fn: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        self._ensure_started()
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self._queue.put((fn, args, kwargs, future))
        return await future

    async def _worker(self) -> None:
        while True:
            fn, args, kwargs, future = await self._queue.get()
            try:
                if not future.cancelled():
                    future.set_result(await fn(*args, **kwargs))
            except asyncio.CancelledError:
                if not future.done():
                    future.cancel()
                raise
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)
            finally:
                self._queue.task_done()

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._started = False

"""跟踪进行中的 Agent 任务，支持按会话取消。"""
from __future__ import annotations

import asyncio
from typing import Dict, Optional

_lock: asyncio.Lock | None = None
_cancel_events: Dict[str, asyncio.Event] = {}


def _job_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def register_job(session_id: str) -> asyncio.Event:
    """注册新任务；若同会话已有任务在跑，先标记取消旧任务。"""
    async with _job_lock():
        old = _cancel_events.get(session_id)
        if old is not None:
            old.set()
        ev = asyncio.Event()
        _cancel_events[session_id] = ev
        return ev


async def cancel_job(session_id: str) -> bool:
    async with _job_lock():
        ev = _cancel_events.get(session_id)
        if ev is None:
            return False
        ev.set()
        return True


async def clear_job(session_id: str) -> None:
    async with _job_lock():
        _cancel_events.pop(session_id, None)


def is_cancelled(cancel_event: Optional[asyncio.Event]) -> bool:
    return cancel_event is not None and cancel_event.is_set()

"""跟踪进行中的 Agent 任务，支持按会话取消，并杀掉已登记的子进程（如 Rscript）。"""
from __future__ import annotations

import asyncio
import os
import signal
import threading
from typing import Dict, Optional, Set

_lock: asyncio.Lock | None = None
_cancel_events: Dict[str, asyncio.Event] = {}
_thread_flags: Dict[str, threading.Event] = {}
_session_pids: Dict[str, Set[int]] = {}
_pid_lock = threading.Lock()


def _job_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def register_job(session_id: str) -> asyncio.Event:
    """注册新任务；若同会话已有任务在跑，先标记取消旧任务并杀其子进程。"""
    async with _job_lock():
        old = _cancel_events.get(session_id)
        if old is not None:
            old.set()
        old_flag = _thread_flags.get(session_id)
        if old_flag is not None:
            old_flag.set()
        kill_session_processes(session_id)

        ev = asyncio.Event()
        flag = threading.Event()
        _cancel_events[session_id] = ev
        _thread_flags[session_id] = flag
        return ev


def get_thread_cancel_flag(session_id: str) -> threading.Event | None:
    """供线程池内的长任务轮询（与 asyncio.Event 同步）。"""
    return _thread_flags.get(session_id)


async def cancel_job(session_id: str) -> bool:
    async with _job_lock():
        ev = _cancel_events.get(session_id)
        flag = _thread_flags.get(session_id)
        if ev is None and flag is None:
            return False
        if ev is not None:
            ev.set()
        if flag is not None:
            flag.set()
        kill_session_processes(session_id)
        return True


async def clear_job(session_id: str) -> None:
    async with _job_lock():
        _cancel_events.pop(session_id, None)
        _thread_flags.pop(session_id, None)
        with _pid_lock:
            _session_pids.pop(session_id, None)


def is_cancelled(cancel_event: Optional[asyncio.Event]) -> bool:
    return cancel_event is not None and cancel_event.is_set()


def register_process(session_id: str | None, pid: int | None) -> None:
    if not session_id or not pid or pid <= 0:
        return
    with _pid_lock:
        _session_pids.setdefault(session_id, set()).add(int(pid))


def unregister_process(session_id: str | None, pid: int | None) -> None:
    if not session_id or not pid:
        return
    with _pid_lock:
        pids = _session_pids.get(session_id)
        if not pids:
            return
        pids.discard(int(pid))
        if not pids:
            _session_pids.pop(session_id, None)


def kill_session_processes(session_id: str | None) -> int:
    """尽力杀掉该会话登记的子进程（含进程组）。返回尝试 kill 的数量。"""
    if not session_id:
        return 0
    with _pid_lock:
        pids = list(_session_pids.get(session_id) or ())
        _session_pids.pop(session_id, None)
    killed = 0
    for pid in pids:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(pid, sig)
                killed += 1
                break
            except ProcessLookupError:
                break
            except PermissionError:
                try:
                    os.kill(pid, sig)
                    killed += 1
                    break
                except Exception:
                    continue
            except Exception:
                try:
                    os.kill(pid, sig)
                    killed += 1
                    break
                except Exception:
                    continue
    return killed

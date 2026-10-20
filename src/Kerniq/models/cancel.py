"""Interrupt an in-flight model call when the user hits Stop.

Providers poll this while a socket is open. The orchestrator also cancels the
task, so a provider that never polls still unblocks.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Optional

from Kerniq.interfaces.models import Message, MessageRole, ModelResponse


class StreamCancelled(Exception):
    """The user stopped the run while a request was in flight."""


def cancel_requested(cancel_check) -> bool:
    if not callable(cancel_check):
        return False
    try:
        return bool(cancel_check())
    except Exception:
        return False


def cancelled_response(content: str = "", metadata: Optional[dict] = None) -> ModelResponse:
    meta = {"cancelled": True}
    if metadata:
        meta.update(metadata)
    return ModelResponse(
        messages=[Message(role=MessageRole.ASSISTANT, content=content or "")],
        finish_reason="cancelled",
        metadata=meta,
    )


async def await_unless_cancelled(coro, cancel_check, interval: float = 0.25):
    """Await `coro`, but raise StreamCancelled as soon as cancel_check flips.

    The coroutine is a child task so a blocked socket read is cancelled too.
    The poll uses a shield: a timeout must not cancel the request itself.
    """
    task = asyncio.create_task(coro)
    try:
        while not task.done():
            if cancel_requested(cancel_check):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(task, 1.5)
                raise StreamCancelled()
            try:
                await asyncio.wait_for(asyncio.shield(task), interval)
            except asyncio.TimeoutError:
                continue
        return task.result()
    except asyncio.CancelledError:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        raise


async def next_stream_line(iterator, response, cancel_check, interval: float = 0.25):
    """Next body line. Raises StreamCancelled or StopAsyncIteration.

    Polls even when the model has not produced a token yet (prefill / thinking).
    The read itself is one task. Timing out the poll must not cancel that read:
    cancelling ``__anext__`` closes the HTTP stream, and Stop then hangs in
    ``aclose`` while the server keeps generating.
    """
    pending = None
    try:
        while True:
            if cancel_requested(cancel_check):
                if pending is not None and not pending.done():
                    pending.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await pending
                with contextlib.suppress(Exception):
                    await response.aclose()
                raise StreamCancelled()
            if pending is None or pending.done():
                pending = asyncio.create_task(iterator.__anext__())
            done, _pending = await asyncio.wait({pending}, timeout=interval)
            if pending not in done:
                continue
            try:
                return pending.result()
            except StopAsyncIteration:
                raise
            finally:
                pending = None
    except asyncio.CancelledError:
        if pending is not None and not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await pending
        with contextlib.suppress(Exception):
            await response.aclose()
        raise

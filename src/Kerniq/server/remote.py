"""Talk to a Kerniq that is already running somewhere else.

The API key authenticates. It does not find the server. The console on the
other machine has to be given the address.
"""

from __future__ import annotations

import sys
from typing import Optional

import httpx


def remote_required_message(has_url: bool, has_key: bool) -> str:
    if not has_url:
        return (
            "A remote console has to know the server address. "
            "Pass --server http://HOST:PORT or set KERNIQ_SERVER."
        )
    if not has_key:
        return "Pass --api-key or set KERNIQ_API_KEY. The key is not an address."
    return ""


async def run_remote(
    base_url: str,
    api_key: str,
    task: str,
    workspace: Optional[str] = None,
) -> int:
    problem = remote_required_message(bool((base_url or "").strip()), bool((api_key or "").strip()))
    if problem:
        print(problem, file=sys.stderr)
        return 2
    url = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    timeout = httpx.Timeout(30.0, read=130.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            started = await client.post(
                url + "/api/remote/run",
                headers=headers,
                json={"task": task, "workspace": workspace or ""},
            )
        except httpx.HTTPError as exc:
            print(f"Cannot reach {url}: {exc.__class__.__name__}", file=sys.stderr)
            return 1
        if started.status_code == 401:
            print("The API key was rejected.", file=sys.stderr)
            return 1
        if started.status_code >= 400:
            print(started.text[:500], file=sys.stderr)
            return 1
        body = started.json()
        run_id = str(body.get("run_id") or "")
        if body.get("queued"):
            print(f"Queued at position {body.get('position')}.")
        if not run_id:
            print("The server did not start a run.", file=sys.stderr)
            return 1
        cursor = 0
        while True:
            try:
                page = await client.get(
                    url + "/api/remote/events",
                    headers=headers,
                    params={"run_id": run_id, "cursor": str(cursor)},
                )
            except httpx.HTTPError as exc:
                print(f"Lost the server: {exc.__class__.__name__}", file=sys.stderr)
                return 1
            if page.status_code >= 400:
                print(page.text[:500], file=sys.stderr)
                return 1
            payload = page.json()
            for event in payload.get("events") or []:
                kind = event.get("type")
                if kind == "assistant" and event.get("content"):
                    print(event.get("content"))
                elif kind == "status" and event.get("text"):
                    print(event.get("text"))
                elif kind == "tool" and event.get("name"):
                    print(f"tool {event.get('name')}: {event.get('status')}")
            cursor += len(payload.get("events") or [])
            if payload.get("done"):
                return 1 if payload.get("error") else 0
            import asyncio
            await asyncio.sleep(0.4)

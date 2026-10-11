"""CLI entry: python -m agent_platform

Sync wrapper so Windows / console_scripts always await async code correctly.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Import the function from the CLI module (not the package attribute shadowing)
    from agent_platform.interfaces_runtime.cli.main import main as cli_main

    if inspect.iscoroutinefunction(cli_main):
        coro = cli_main(list(argv)) if argv is not None else cli_main()
        return int(asyncio.run(coro) or 0)

    result = cli_main(list(argv)) if argv is not None else cli_main()
    if inspect.iscoroutine(result):
        return int(asyncio.run(result) or 0)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())

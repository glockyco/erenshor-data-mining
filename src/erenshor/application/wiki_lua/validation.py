"""Compile check for generated Scribunto Lua modules."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path


class LuaValidationError(RuntimeError):
    """Raised when generated Lua does not compile as Lua 5.1."""


Which = Callable[[str], str | None]
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def validate_lua_modules(
    paths: Sequence[Path],
    *,
    which: Which = shutil.which,
    run: Runner | None = None,
) -> None:
    """Compile every module with Lua 5.1's `luac -p` in one process.

    Scribunto runs Lua 5.1, so its compiler is the exact check, including the
    limits of large table constructors. The check reads the modules and never
    changes them.
    """
    if not paths:
        return
    runner = run or _run_command
    luac = which("luac")
    if luac is None:
        raise LuaValidationError("Generated Lua needs luac from Lua 5.1. Run the command in the dev shell.")
    version = runner([luac, "-v"])
    if version.returncode != 0 or not _detail(version).startswith("Lua 5.1"):
        raise LuaValidationError(f"Generated Lua needs luac from Lua 5.1, not {luac}: {_detail(version)}")
    result = runner([luac, "-p", *(str(path) for path in paths)])
    if result.returncode != 0:
        raise LuaValidationError(f"luac rejected generated Lua: {_detail(result)}")


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _detail(result: subprocess.CompletedProcess[str]) -> str:
    output = result.stderr.strip() or result.stdout.strip()
    return output if output else f"exit code {result.returncode}"

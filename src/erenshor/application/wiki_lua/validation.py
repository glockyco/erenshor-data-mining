"""Validation helpers for generated Scribunto Lua modules."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class LuaValidationError(RuntimeError):
    """Raised when generated Lua cannot be validated locally."""


@dataclass(frozen=True)
class LuaValidationResult:
    """Result of validating a generated Lua module."""

    path: Path
    tool: str


Which = Callable[[str], str | None]
Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def validate_lua_module(
    path: Path,
    *,
    which: Which = shutil.which,
    run: Runner | None = None,
) -> LuaValidationResult:
    """Validate generated Lua module syntax using the best local tool available.

    `luac -p` is the preferred syntax-only validator. When it is not installed,
    use StyLua's Lua 5.1 parser with AST verification. StyLua formats the file
    in place, so callers should only use this fallback for generated output.
    """
    runner = run or _run_command

    luac = which("luac")
    if luac is not None:
        _run_validator(runner, [luac, "-p", str(path)], tool="luac", path=path)
        return LuaValidationResult(path=path, tool="luac")

    stylua = which("stylua")
    if stylua is not None:
        _run_validator(runner, [stylua, "--syntax", "Lua51", "--verify", str(path)], tool="stylua", path=path)
        return LuaValidationResult(path=path, tool="stylua")

    pnpm = which("pnpm")
    if pnpm is not None:
        _run_validator(
            runner,
            [pnpm, "exec", "stylua", "--syntax", "Lua51", "--verify", str(path)],
            tool="stylua",
            path=path,
        )
        return LuaValidationResult(path=path, tool="stylua")

    raise LuaValidationError(
        "Generated Lua validation requires luac or StyLua. Install Lua 5.1+ "
        + "or run `pnpm install` so `pnpm exec stylua` is available."
    )


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _run_validator(runner: Runner, command: list[str], *, tool: str, path: Path) -> None:
    result = runner(command)
    if result.returncode == 0:
        return

    detail = _validation_detail(result)
    raise LuaValidationError(f"{tool} failed to validate {path}: {detail}")


def _validation_detail(result: subprocess.CompletedProcess[str]) -> str:
    output = result.stderr.strip() or result.stdout.strip()
    return output if output else f"exit code {result.returncode}"

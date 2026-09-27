"""Preflight the optional C# file before sending eval code to the game."""

from __future__ import annotations

from typing import Any

from erenshor.cli.preconditions.base import PreconditionResult
from erenshor.cli.preconditions.checks.inputs import option_path


def eval_source(context: dict[str, Any]) -> PreconditionResult:
    """Require exactly one code source and a real file when specified."""
    code = context.get("code")
    file = context.get("file")
    if bool(code) == bool(file):
        return PreconditionResult(False, "eval_source", "Provide exactly one C# code argument or --file")
    if file:
        return option_path("file")(context)
    return PreconditionResult(True, "eval_source", "C# code argument supplied")

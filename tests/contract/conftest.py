"""Fixtures for hermetic .NET contract tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


_DOTNET = shutil.which("dotnet")
_CODE_FACTS_TOOL = Path(__file__).resolve().parents[2] / "src" / "tools" / "CodeFacts"


def build_dotnet(project: Path, *extra: str) -> None:
    """Build a .NET project in Release, surfacing MSBuild output on failure."""
    assert _DOTNET is not None, "dotnet SDK not on PATH; gate tests with skipif"
    proc = subprocess.run(
        [_DOTNET, "build", str(project), "-c", "Release", *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"dotnet build failed for {project} (exit {proc.returncode})\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def dotnet_build() -> Callable[..., None]:
    """Expose the diagnostic .NET build helper to contract test modules."""
    return build_dotnet


@pytest.fixture(scope="session")
def code_facts_tool() -> Path:
    """Build the CodeFacts analyzer once per session; return its project dir."""
    build_dotnet(_CODE_FACTS_TOOL)
    return _CODE_FACTS_TOOL

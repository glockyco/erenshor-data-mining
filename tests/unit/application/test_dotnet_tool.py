"""The .NET tool runner names a missing SDK and shows why a build failed."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from erenshor.application.dotnet_tool import run_dotnet_tool


def test_missing_sdk_is_named_before_anything_runs() -> None:
    with (
        patch("erenshor.application.dotnet_tool.shutil.which", return_value=None),
        patch("erenshor.application.dotnet_tool.subprocess.run") as run,
        pytest.raises(RuntimeError, match="dotnet SDK not found on PATH"),
    ):
        run_dotnet_tool(Path("src/tools/CodeFacts"), [])

    run.assert_not_called()


def test_failed_build_reports_its_output_and_skips_the_run() -> None:
    failed_build = subprocess.CompletedProcess(["dotnet", "build"], 1, stdout="error CS1002: ; expected", stderr="")
    with (
        patch("erenshor.application.dotnet_tool.shutil.which", return_value="/bin/dotnet"),
        patch("erenshor.application.dotnet_tool.subprocess.run", return_value=failed_build) as run,
        pytest.raises(RuntimeError, match="error CS1002"),
    ):
        run_dotnet_tool(Path("src/tools/CodeFacts"), ["game.dll"])

    assert run.call_count == 1

"""Build and run the repository's .NET analysis tools.

The CodeFacts and ExportSurface analyzers are .NET console projects that the
Python pipeline invokes. This module owns the two steps they share: finding
the SDK and building the project before it runs.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run_dotnet_tool(project: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Build ``project`` in Release and run it with ``args``.

    Returns the completed run so the caller can interpret the tool's exit code
    and output. Raises when the SDK is not on PATH or when the build fails,
    and includes the build output in the error.
    """
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        raise RuntimeError("dotnet SDK not found on PATH. The Nix development shell provides it.")

    build = subprocess.run(
        [dotnet, "build", str(project), "-c", "Release"],
        capture_output=True,
        text=True,
        check=False,
    )
    if build.returncode != 0:
        raise RuntimeError(
            f"dotnet build of {project} failed (exit {build.returncode}).\n"
            f"stderr: {build.stderr.strip()}\n"
            f"output: {build.stdout.strip()}"
        )

    return subprocess.run(
        [dotnet, "run", "-c", "Release", "--no-build", "--project", str(project), "--", *args],
        capture_output=True,
        text=True,
        check=False,
    )

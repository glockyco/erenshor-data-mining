"""Live contract canary for the AssetRipper command line.

AssetRipper renames launch options between releases, and the failure mode is
silent from the pipeline's perspective: the process exits immediately, the HTTP
API never answers, and `extract rip` reports a startup timeout half a minute
later. Assert the flags the adapter passes still exist in the installed build.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from erenshor.infrastructure.assetripper import AssetRipper
from erenshor.infrastructure.config import load_config
from erenshor.infrastructure.config.paths import PathResolutionError

pytestmark = pytest.mark.canary


def test_installed_assetripper_accepts_the_launch_flags() -> None:
    """Every flag in the launch command is documented by the installed build."""
    config = load_config()
    repo_root = Path(__file__).resolve().parents[2]
    try:
        executable = config.global_.assetripper.resolved_path(repo_root)
    except PathResolutionError as error:
        pytest.skip(str(error))

    ripper = AssetRipper(executable_path=executable, port=8080)
    usage = subprocess.run(
        [str(executable), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout

    flags = [argument for argument in ripper.launch_command() if argument.startswith("--")]
    assert flags, "launch command must be flag-driven"
    for flag in flags:
        assert flag in usage, f"AssetRipper no longer accepts {flag}:\n{usage}"

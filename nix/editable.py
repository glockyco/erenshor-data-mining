"""Select the current checkout for the Nix editable installation."""

import os
import sys
from pathlib import Path


def install() -> None:
    current = Path.cwd().resolve()
    for root in (current, *current.parents):
        if (root / ".git").exists() and (root / "src/erenshor/__init__.py").is_file():
            sys.path.append(str(root / "src"))
            return

    # Commands outside a checkout still use the shell's editable installation.
    shell_root = os.environ.get("REPO_ROOT")
    if shell_root and (Path(shell_root) / "src/erenshor/__init__.py").is_file():
        sys.path.append(str(Path(shell_root) / "src"))

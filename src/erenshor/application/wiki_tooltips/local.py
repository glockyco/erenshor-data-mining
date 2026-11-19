"""Run tooltip parity on a disposable local MediaWiki project."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.application.wiki_tooltips.report import ParityPaths


def check(paths: ParityPaths) -> None:
    """Import and render the selected build without touching the warm wiki."""
    if not paths.evidence.is_file():
        raise ValueError(f"Capture game tooltip evidence first: {paths.evidence}")
    project = f"wiki-tooltip-{uuid.uuid4().hex[:12]}"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base_url = f"http://localhost:{port}"
    environment = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": project,
        "BASE_URL": base_url,
        "WIKI_HOST_PORT": str(port),
        "WIKI_DB_MOUNT_TYPE": "volume",
        "WIKI_DB_MOUNT_SOURCE": "clean-db",
        "WIKI_IMAGES_MOUNT_TYPE": "volume",
        "WIKI_IMAGES_MOUNT_SOURCE": "clean-images",
        "WIKI_RUNTIME_MOUNT_TYPE": "volume",
        "WIKI_RUNTIME_MOUNT_SOURCE": "clean-runtime",
    }
    manifest = paths.output / f"import-{project}" / "manifest.json"
    try:
        subprocess.run(("bash", "wiki-dev/bootstrap.sh"), cwd=paths.root, env=environment, check=True)
        subprocess.run(
            (
                sys.executable,
                "wiki-dev/import_pages.py",
                "--base-url",
                base_url,
                "--generated-wiki",
                str(paths.wiki),
                "--manifest-file",
                str(manifest),
            ),
            cwd=paths.root,
            env=environment,
            check=True,
        )
        subprocess.run(
            (
                sys.executable,
                "wiki-dev/tooltip_parity.py",
                "--base-url",
                base_url,
                "--root",
                str(paths.root),
                "--database",
                str(paths.database),
                "--wiki",
                str(paths.wiki),
            ),
            cwd=paths.root,
            env=environment,
            check=True,
        )
    finally:
        subprocess.run(
            (
                "docker",
                "compose",
                "-f",
                "wiki-dev/compose.yml",
                "--project-name",
                project,
                "down",
                "--volumes",
                "--remove-orphans",
            ),
            cwd=paths.root,
            env=environment,
            check=True,
        )

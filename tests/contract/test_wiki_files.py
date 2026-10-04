"""Every repository wiki source has a deployment path."""

from __future__ import annotations

import subprocess
from pathlib import Path

from erenshor.application.wiki_deploy.manifest import build_repo_page_manifest
from erenshor.application.wiki_interface.gadgets import gadget_source_pages, load_gadget_spec

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_wiki_files_have_deploy_paths() -> None:
    manifest = build_repo_page_manifest(REPO_ROOT, "main", include_templates=True, include_content_pages=True)
    page_sources = {entry.source_path for entry in manifest.entries}
    gadget_sources = {
        page.source_path.as_posix() for page in gadget_source_pages(load_gadget_spec(REPO_ROOT), REPO_ROOT)
    }
    deployable = page_sources | gadget_sources | {"wiki/gadgets/gadgets.toml"}

    # Include new files before staging, so a copy cannot slip into the next commit.
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "wiki/"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    files = {path for path in result.stdout.splitlines() if (REPO_ROOT / path).is_file()}
    unsupported = sorted(
        path
        for path in files
        if path not in deployable and not (path.startswith("wiki/modules/") and path.endswith("/testcases.lua"))
    )

    assert not unsupported, "Wiki files without a deploy path:\n" + "\n".join(unsupported)

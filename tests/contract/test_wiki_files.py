"""Rules that every repository wiki source follows."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from erenshor.application.wiki_deploy.manifest import build_repo_page_manifest
from erenshor.application.wiki_interface.gadgets import gadget_source_pages, load_gadget_spec

REPO_ROOT = Path(__file__).resolve().parents[2]

# Cargo's parser functions (#cargo_declare, #cargo_attach, #cargo_store,
# #cargo_query, and the rest) and its Lua interface. MediaWiki matches parser
# function names without regard to case.
_CARGO_USE = re.compile(r"#cargo_|\bmw\.ext\.cargo\b", re.IGNORECASE)


def _wiki_files() -> set[str]:
    # Include new files before staging, so a file cannot slip into the next commit unchecked.
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "wiki/"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {path for path in result.stdout.splitlines() if (REPO_ROOT / path).is_file()}


def test_wiki_files_have_deploy_paths() -> None:
    manifest = build_repo_page_manifest(REPO_ROOT, "main", include_templates=True, include_content_pages=True)
    page_sources = {entry.source_path for entry in manifest.entries}
    gadget_sources = {
        page.source_path.as_posix() for page in gadget_source_pages(load_gadget_spec(REPO_ROOT), REPO_ROOT)
    }
    deployable = page_sources | gadget_sources | {"wiki/gadgets/gadgets.toml"}

    unsupported = sorted(
        path
        for path in _wiki_files()
        if path not in deployable and not (path.startswith("wiki/modules/") and path.endswith("/testcases.lua"))
    )

    assert not unsupported, "Wiki files without a deploy path:\n" + "\n".join(unsupported)


def test_wiki_files_use_no_cargo() -> None:
    cargo_users = sorted(
        path for path in _wiki_files() if _CARGO_USE.search((REPO_ROOT / path).read_text(encoding="utf-8"))
    )

    assert not cargo_users, "Wiki files that use Cargo:\n" + "\n".join(cargo_users)

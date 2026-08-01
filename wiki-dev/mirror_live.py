#!/usr/bin/env python3
"""Mirror live wiki content into the local development stack.

`import_pages.py` imports only repository-managed sources: modules, templates,
interface pages, and fixtures. That is the right scope for proving repo changes,
but it leaves the local wiki with a few hundred pages against the live wiki's
several thousand, so anything that depends on real content (main page links,
category sizes, navigation, search) cannot be reviewed locally.

This script fills that gap. It pulls live content through the MediaWiki export
API and imports it with `importDump.php`, optionally mirroring files as well.

It is a review aid, not a source of truth:

- It only ever reads from live. It cannot write there.
- It never touches repository-managed titles, so a later `import_pages.py` run
  still governs those and its manifest stays authoritative.
- Mirrored pages keep live revision history and attribution.

Usage from the repository root:

    uv run python wiki-dev/mirror_live.py --dry-run
    uv run python wiki-dev/mirror_live.py                # pages only
    uv run python wiki-dev/mirror_live.py --with-files   # pages and images
    uv run python wiki-dev/mirror_live.py --namespaces 0 14
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

LIVE_API = "https://erenshor.wiki.gg/api.php"
CONTAINER = "wiki-dev-mediawiki-1"
USER_AGENT = "erenshor-wiki-dev-mirror/1.0 (local development mirror)"

# 0 main, 6 File descriptions, 10 Template, 14 Category, 828 Module.
# Templates and modules are repository-managed, so they are excluded by default:
# mirroring them would mask local changes under whatever live currently has.
DEFAULT_NAMESPACES = (0, 6, 14)

EXPORT_BATCH = 50  # anonymous API cap for multi-value parameters
FILE_BATCH_PAUSE = 0.05


def _get(url: str, params: dict[str, str]) -> bytes:
    request = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data: bytes = response.read()
    return data


def _json_get(url: str, params: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(_get(url, {**params, "format": "json"}))
    return payload


def live_titles(namespace: int) -> list[str]:
    """Every non-redirect title in one live namespace."""
    titles: list[str] = []
    cont: dict[str, str] = {}
    while True:
        payload = _json_get(
            LIVE_API,
            {
                "action": "query",
                "list": "allpages",
                "apnamespace": str(namespace),
                "aplimit": "500",
                "apfilterredir": "all",
                **cont,
            },
        )
        titles += [page["title"] for page in payload["query"]["allpages"]]
        if "continue" not in payload:
            return titles
        cont = {key: str(value) for key, value in payload["continue"].items()}


def export_batch(titles: list[str]) -> bytes:
    """Export pages as MediaWiki XML, current revision only."""
    body = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": "|".join(titles),
            "export": "1",
            "exportnowrap": "1",
            "format": "json",
        }
    ).encode()
    request = urllib.request.Request(LIVE_API, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        data: bytes = response.read()
    return data


def repo_managed_titles(root: Path) -> set[str]:
    """Titles governed by import_pages.py, which must not be overwritten."""
    sys.path.insert(0, str(root / "wiki-dev"))
    import import_pages  # path-injected sibling script

    pages = import_pages.discover_pages(root) + import_pages.discover_interface_pages(root)
    return {page.title for page in pages}


def docker_exec(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["docker", "exec", CONTAINER, *args], check=check)


def import_dump(xml_path: Path, container_path: str) -> None:
    subprocess.run(["docker", "cp", str(xml_path), f"{CONTAINER}:{container_path}"], check=True)
    docker_exec(
        [
            "php",
            "/var/www/html/maintenance/run.php",
            "importDump",
            "--no-updates",
            "--username-prefix=live",
            container_path,
        ],
        check=True,
    )
    docker_exec(["rm", "-f", container_path], check=False)


def mirror_files(staging: Path, limit: int | None) -> int:
    """Download live files and import them with importImages.php."""
    staging.mkdir(parents=True, exist_ok=True)
    cont: dict[str, str] = {}
    downloaded = 0
    while True:
        payload = _json_get(
            LIVE_API,
            {
                "action": "query",
                "list": "allimages",
                "ailimit": "500",
                "aiprop": "url|size",
                **cont,
            },
        )
        for image in payload["query"]["allimages"]:
            if limit is not None and downloaded >= limit:
                cont = {}
                break
            target = staging / image["name"].replace("/", "_")
            if target.exists():
                continue
            try:
                request = urllib.request.Request(image["url"], headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=120) as response:
                    target.write_bytes(response.read())
                downloaded += 1
            except Exception as error:
                print(f"  file failed: {image['name']}: {error}", file=sys.stderr)
            time.sleep(FILE_BATCH_PAUSE)
        if limit is not None and downloaded >= limit:
            break
        if "continue" not in payload:
            break
        cont = {key: str(value) for key, value in payload["continue"].items()}

    subprocess.run(["docker", "cp", str(staging), f"{CONTAINER}:/tmp/mirror-files"], check=True)
    docker_exec(
        [
            "php",
            "/var/www/html/maintenance/run.php",
            "importImages",
            "--overwrite",
            "--comment=Mirrored from the live wiki for local review",
            "/tmp/mirror-files",
        ],
        check=True,
    )
    docker_exec(["rm", "-rf", "/tmp/mirror-files"], check=False)
    return downloaded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report, change nothing")
    parser.add_argument(
        "--namespaces",
        type=int,
        nargs="+",
        default=list(DEFAULT_NAMESPACES),
        help=f"namespace ids to mirror (default: {' '.join(map(str, DEFAULT_NAMESPACES))})",
    )
    parser.add_argument(
        "--with-files",
        action="store_true",
        help="also mirror uploaded files (roughly 800 MB for the whole wiki)",
    )
    parser.add_argument("--file-limit", type=int, default=None, help="stop after this many files")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    if shutil.which("docker") is None:
        print("docker not found on PATH", file=sys.stderr)
        return 1

    protected = repo_managed_titles(root)
    print(f"repository-managed titles held back: {len(protected)}")

    planned: list[str] = []
    for namespace in args.namespaces:
        titles = live_titles(namespace)
        kept = [title for title in titles if title not in protected]
        print(f"  ns {namespace:>3}: {len(titles):>5} live, {len(kept):>5} to mirror")
        planned += kept

    print(f"total pages to mirror: {len(planned)}")
    if args.dry_run:
        print("dry run, nothing imported")
        return 0

    staging = root / "wiki-dev" / "runtime" / "mirror"
    staging.mkdir(parents=True, exist_ok=True)
    dump = staging / "live-export.xml"

    # Each export response is a complete <mediawiki> document. Concatenating
    # them yields multiple roots, which is not valid XML, so keep the preamble
    # from the first response, append only <page> elements after that, and
    # close the document once at the end.
    preamble = b""
    pages_written = 0
    with dump.open("wb") as handle:
        for index in range(0, len(planned), EXPORT_BATCH):
            batch = planned[index : index + EXPORT_BATCH]
            chunk = export_batch(batch)
            if b"<page>" not in chunk:
                print(f"\n  batch at {index} returned no pages: {chunk[:160]!r}")
                continue
            if not preamble:
                preamble = chunk[: chunk.index(b"<page>")]
                handle.write(preamble)
            body = chunk[chunk.index(b"<page>") : chunk.rindex(b"</page>") + 7]
            handle.write(body)
            pages_written += body.count(b"<page>")
            done = min(index + EXPORT_BATCH, len(planned))
            print(f"  exported {done}/{len(planned)}", end="\r", flush=True)
        handle.write(b"\n</mediawiki>\n")
    print(f"\nexport written: {dump} ({dump.stat().st_size // 1024} KB, {pages_written} pages)")

    import_dump(dump, "/tmp/live-export.xml")

    if args.with_files:
        count = mirror_files(staging / "files", args.file_limit)
        print(f"files mirrored: {count}")

    docker_exec(["php", "/var/www/html/maintenance/run.php", "rebuildall"], check=False)
    # importDump --no-updates leaves site_stats untouched, so Special:Statistics
    # and {{NUMBEROFARTICLES}} would still report the pre-mirror counts.
    docker_exec(
        ["php", "/var/www/html/maintenance/run.php", "initSiteStats", "--update"],
        check=False,
    )
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

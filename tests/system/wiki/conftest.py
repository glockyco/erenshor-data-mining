"""Shared fixtures for local wiki tests: the real MediaWiki harness, and a browser with first-failure diagnostics."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, cast

import httpx
import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Request, sync_playwright

from erenshor.infrastructure.wiki import MediaWikiClient

if TYPE_CHECKING:
    import pluggy

_REPORT_ROOT = Path("artifacts/test-reports/wiki-diagnostics")
_FIRST_FAILURE_DIRECTORY = _REPORT_ROOT / "first-failure"
_failure_state = {"captured": False}
_CALL_REPORT = pytest.StashKey[pytest.TestReport]()


def pytest_sessionstart(session: pytest.Session) -> None:
    """Clear stale diagnostics so a passing run cannot expose old failures."""
    del session
    _failure_state["captured"] = False
    shutil.rmtree(_REPORT_ROOT, ignore_errors=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[None],
) -> Generator[None, pluggy.Result[pytest.TestReport], None]:  # noqa: UP043
    """Expose call outcomes to yield fixtures before browser teardown."""
    del call
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        item.stash[_CALL_REPORT] = report


def _request_failure(request: Request) -> dict[str, str]:
    return {
        "failure": request.failure or "unknown failure",
        "method": request.method,
        "resource_type": request.resource_type,
        "url": request.url,
    }


def _compose_logs() -> str:
    project = os.environ.get("ERENSHOR_WIKI_COMPOSE_PROJECT", "wiki-dev")
    try:
        completed = subprocess.run(
            [
                "docker",
                "compose",
                "--project-name",
                project,
                "--file",
                "wiki-dev/compose.yml",
                "logs",
                "--no-color",
            ],
            cwd=Path.cwd(),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"Unable to capture Docker Compose logs: {error}\n"
    return (
        f"command exit code: {completed.returncode}\n"
        f"--- stdout ---\n{completed.stdout}\n"
        f"--- stderr ---\n{completed.stderr}"
    )


def _write_page_artifact(filename: str, action: Callable[[Path], object]) -> None:
    path = _FIRST_FAILURE_DIRECTORY / filename
    try:
        _ = action(path)
    except Exception as error:
        _ = path.with_suffix(path.suffix + ".error.txt").write_text(
            f"{type(error).__name__}: {error}\n",
            encoding="utf-8",
        )


def _capture_first_failure(
    page: Page,
    nodeid: str,
    console_messages: list[dict[str, str]],
    failed_requests: list[dict[str, str]],
    page_errors: list[str],
) -> None:
    if _failure_state["captured"]:
        return
    _failure_state["captured"] = True
    _FIRST_FAILURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    metadata = {
        "nodeid": nodeid,
        "url": page.url,
        "wiki_base_url": os.environ.get("ERENSHOR_WIKI_BASE_URL", "http://localhost:8088"),
        "compose_project": os.environ.get("ERENSHOR_WIKI_COMPOSE_PROJECT", "wiki-dev"),
    }
    _ = (_FIRST_FAILURE_DIRECTORY / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _ = (_FIRST_FAILURE_DIRECTORY / "console.json").write_text(
        json.dumps(console_messages, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _ = (_FIRST_FAILURE_DIRECTORY / "failed-requests.json").write_text(
        json.dumps(failed_requests, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _ = (_FIRST_FAILURE_DIRECTORY / "page-errors.json").write_text(
        json.dumps(page_errors, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _ = (_FIRST_FAILURE_DIRECTORY / "service.log").write_text(_compose_logs(), encoding="utf-8")
    _write_page_artifact("page.html", lambda path: path.write_text(page.content(), encoding="utf-8"))
    _write_page_artifact("screenshot.png", lambda path: page.screenshot(path=path, full_page=True))


@pytest.fixture
def browser_page(request: pytest.FixtureRequest) -> Iterator[Page]:
    """Yield one isolated Chromium page and capture the first failing state."""
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as error:
            pytest.skip(f"Playwright Chromium is unavailable: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        console_messages: list[dict[str, str]] = []
        failed_requests: list[dict[str, str]] = []
        page_errors: list[str] = []
        page.on("console", lambda message: console_messages.append({"text": message.text, "type": message.type}))
        page.on("requestfailed", lambda failed: failed_requests.append(_request_failure(failed)))
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            yield page
        finally:
            node = cast("pytest.Item", request.node)
            report = node.stash.get(_CALL_REPORT, None)
            probe = os.environ.get("ERENSHOR_WIKI_DIAGNOSTIC_PROBE") == "1"
            if (report is not None and report.failed) or page_errors or probe:
                _capture_first_failure(
                    page,
                    node.nodeid,
                    console_messages,
                    failed_requests,
                    page_errors,
                )
            browser.close()
        if page_errors:
            pytest.fail(f"Browser page errors: {page_errors}")
        if os.environ.get("ERENSHOR_WIKI_DIAGNOSTIC_PROBE") == "1":
            pytest.fail("Intentional wiki browser diagnostic probe")


def diagnostic_artifact_names() -> set[str]:
    """Return the required first-failure artifact contract."""
    return {
        "console.json",
        "failed-requests.json",
        "metadata.json",
        "page-errors.json",
        "page.html",
        "screenshot.png",
        "service.log",
    }


# --- The real MediaWiki harness in wiki-dev/, shared by every test that needs it. ---

WIKI_BASE_URL = os.environ.get("ERENSHOR_WIKI_BASE_URL", "http://localhost:8088")
API_URL = f"{WIKI_BASE_URL}/api.php"
BOT_USER = "ErenshorBot"
BOT_PASSWORD = "BotDevPassword-2026"
ADMIN_USER = "WikiSysop"
ADMIN_PASSWORD = "DevWikiPassword-2026"
COMPOSE_PROJECT = os.environ.get("ERENSHOR_WIKI_COMPOSE_PROJECT", "wiki-dev")
COMPOSE_FILE = Path(__file__).resolve().parents[3] / "wiki-dev" / "compose.yml"


def _harness_reachable() -> bool:
    try:
        response = httpx.get(
            API_URL,
            params={"action": "query", "meta": "siteinfo", "format": "json"},
            timeout=5.0,
        )
    except (httpx.HTTPError, OSError):
        return False
    if response.status_code != 200:
        return False
    try:
        return "query" in response.json()
    except ValueError:
        return False


def _docker_compose(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            COMPOSE_PROJECT,
            "-f",
            str(COMPOSE_FILE),
            *args,
        ],
        input=stdin.encode() if stdin is not None else None,
        capture_output=True,
        timeout=180,
        check=False,
    )


def _ensure_deploy_bot() -> None:
    result = _docker_compose(
        "exec",
        "-T",
        "mediawiki",
        "php",
        "maintenance/run.php",
        "createAndPromote",
        "--bot",
        "--force",
        BOT_USER,
        BOT_PASSWORD,
    )
    if result.returncode != 0:
        pytest.skip(f"Could not provision deploy bot: {result.stderr.decode(errors='replace')}")


def _delete_pages(titles: list[str]) -> None:
    if not titles:
        return
    _docker_compose(
        "exec",
        "-T",
        "mediawiki",
        "php",
        "maintenance/run.php",
        "deleteBatch.php",
        "-r",
        "integration test cleanup",
        stdin="\n".join(titles) + "\n",
    )


class _PageScope:
    """Tracks live wiki pages a test owns and gives each a clean slate."""

    def __init__(self) -> None:
        self.titles: list[str] = []

    def claim(self, title: str) -> str:
        _delete_pages([title])
        self.titles.append(title)
        return title


@pytest.fixture(scope="module")
def wiki_client() -> Iterator[MediaWikiClient]:
    """A real client logged in as the deploy bot: create, edit, and upload rights."""
    if not _harness_reachable():
        pytest.skip(f"Local MediaWiki harness not reachable at {WIKI_BASE_URL}")
    if shutil.which("docker") is None:
        pytest.skip("Docker is required to provision the deploy bot and clean up test pages")

    _ensure_deploy_bot()

    client = MediaWikiClient(
        api_url=API_URL,
        bot_username=BOT_USER,
        bot_password=BOT_PASSWORD,
    )
    client.login()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="module")
def wiki_administrator() -> Iterator[MediaWikiClient]:
    """A real client logged in as the install-time administrator: move, delete, and undelete rights.

    Production code (`image_publication_run.py`) calls `move_page`, `delete_page`,
    and `undelete_page` on this role, never on the bot client, because a bot
    password does not carry `movefile`/`suppressredirect`/`delete` by default.
    """
    if not _harness_reachable():
        pytest.skip(f"Local MediaWiki harness not reachable at {WIKI_BASE_URL}")
    if shutil.which("docker") is None:
        pytest.skip("Docker is required to clean up test pages")

    client = MediaWikiClient(
        api_url=API_URL,
        bot_username=ADMIN_USER,
        bot_password=ADMIN_PASSWORD,
    )
    client.login()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def pages(wiki_client: MediaWikiClient) -> Iterator[_PageScope]:
    scope = _PageScope()
    try:
        yield scope
    finally:
        _delete_pages(scope.titles)

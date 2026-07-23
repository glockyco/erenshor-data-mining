"""Shared browser fixture with first-failure diagnostics for local wiki tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Request, sync_playwright

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

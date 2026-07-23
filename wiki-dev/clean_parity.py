#!/usr/bin/env python3
"""Prove a clean local MediaWiki stack matches the warm developer wiki."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, cast


class _AcceptanceSnapshot(Protocol):
    def to_payload(self) -> dict[str, object]: ...


def _load_acceptance() -> ModuleType:
    path = Path(__file__).resolve().with_name("acceptance.py")
    spec = importlib.util.spec_from_file_location("wiki_dev_clean_acceptance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load acceptance helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_acceptance = _load_acceptance()
BROWSER_COUNTER_KEYS = cast("tuple[str, ...]", _acceptance.BROWSER_COUNTER_KEYS)
capture_acceptance = cast(
    "Callable[[Path, str, Mapping[str, int]], _AcceptanceSnapshot]",
    _acceptance.capture_acceptance,
)
compare_acceptance = cast(
    "Callable[[_AcceptanceSnapshot, _AcceptanceSnapshot], list[str]]",
    _acceptance.compare_acceptance,
)


PYTEST_REPORT_SCHEMA = 1
DEFAULT_WARM_BASE_URL = "http://localhost:8088"
DEFAULT_WARM_PROJECT = "wiki-dev"
_PROJECT_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*")


@dataclass(frozen=True, slots=True)
class CommandRecord:
    """One subprocess invoked by the parity harness."""

    argv: tuple[str, ...]
    exit_code: int
    duration_seconds: float


class CommandFailureError(RuntimeError):
    """Raised when one harness subprocess fails."""


class CleanParityHarness:
    """Own the clean stack lifecycle and warm-state invariants."""

    def __init__(
        self,
        *,
        root: Path,
        warm_base_url: str,
        warm_project: str,
        clean_base_url: str,
        clean_project: str,
        clean_port: int,
        work_directory: Path,
    ) -> None:
        self.root = root.resolve()
        self.warm_base_url = warm_base_url.rstrip("/")
        self.warm_project = warm_project
        self.clean_base_url = clean_base_url.rstrip("/")
        self.clean_project = clean_project
        self.clean_port = clean_port
        self.work_directory = work_directory
        self.commands: list[CommandRecord] = []
        self._clean_environment = {
            "COMPOSE_PROJECT_NAME": clean_project,
            "BASE_URL": self.clean_base_url,
            "WIKI_HOST_PORT": str(clean_port),
            "WIKI_DB_MOUNT_TYPE": "volume",
            "WIKI_DB_MOUNT_SOURCE": "clean-db",
            "WIKI_IMAGES_MOUNT_TYPE": "volume",
            "WIKI_IMAGES_MOUNT_SOURCE": "clean-images",
            "WIKI_RUNTIME_MOUNT_TYPE": "volume",
            "WIKI_RUNTIME_MOUNT_SOURCE": "clean-runtime",
        }

    def _run(self, argv: Sequence[str], *, environment: Mapping[str, str] | None = None) -> None:
        command = tuple(str(part) for part in argv)
        process_environment = os.environ.copy()
        if environment is not None:
            process_environment.update(environment)
        started = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=self.root,
            env=process_environment,
            check=False,
        )
        record = CommandRecord(
            argv=command,
            exit_code=int(completed.returncode),
            duration_seconds=round(max(0.0, time.monotonic() - started), 6),
        )
        self.commands.append(record)
        if record.exit_code != 0:
            raise CommandFailureError(f"Command exited with {record.exit_code}: {' '.join(command)}")

    def _browser_report(self, path: Path) -> dict[str, int]:
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read browser test report {path}: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema") != PYTEST_REPORT_SCHEMA:
            raise RuntimeError(f"Browser test report has an unsupported shape: {path}")
        counters: dict[str, int] = {}
        for key in BROWSER_COUNTER_KEYS:
            value = payload.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise RuntimeError(f"Browser test report has invalid {key}: {path}")
            counters[key] = value
        if (
            counters["collected"] <= 0
            or counters["deselected"] != 0
            or counters["skipped"] != 0
            or counters["failed"] != 0
            or counters["exit_code"] != 0
        ):
            raise RuntimeError(f"Browser test report is incomplete or failed: {counters}")
        return counters

    def _validate_stack(
        self,
        *,
        base_url: str,
        compose_project: str,
        manifest_file: Path | None,
        report_file: Path,
        initialize_cargo: bool = False,
    ) -> dict[str, int]:
        import_command = [
            "uv",
            "run",
            "python",
            "wiki-dev/import_pages.py",
            "--base-url",
            base_url,
            "--root",
            str(self.root),
        ]
        if manifest_file is not None:
            import_command.extend(("--manifest-file", str(manifest_file)))
        if initialize_cargo:
            import_command.append("--include-clean-dependencies")
        self._run(import_command)
        if initialize_cargo:
            self._run(
                (
                    "uv",
                    "run",
                    "python",
                    "wiki-dev/cargo_check.py",
                    "--base-url",
                    base_url,
                    "--recreate",
                )
            )
            self._run(
                (
                    "uv",
                    "run",
                    "python",
                    "wiki-dev/null_edit.py",
                    "--base-url",
                    base_url,
                )
            )
        self._run(("uv", "run", "python", "wiki-dev/smoke_test.py", "--base-url", base_url))
        self._run(("uv", "run", "python", "wiki-dev/cargo_check.py", "--base-url", base_url))
        test_environment = {
            "ERENSHOR_WIKI_BASE_URL": base_url,
            "ERENSHOR_WIKI_COMPOSE_PROJECT": compose_project,
        }
        if compose_project == self.clean_project:
            test_environment.update(self._clean_environment)
        self._run(
            (
                "uv",
                "run",
                "pytest",
                "tests/system/wiki/test_wiki_semantic_picker.py",
                "tests/system/wiki/test_wiki_semantic_tooltips.py",
                "-p",
                "erenshor.cli.commands.test",
                "--erenshor-report",
                str(report_file),
            ),
            environment=test_environment,
        )
        return self._browser_report(report_file)

    def _bootstrap_clean_stack(self) -> None:
        self._run(("bash", "wiki-dev/bootstrap.sh"), environment=self._clean_environment)

    def _teardown_clean_stack(self) -> None:
        self._run(
            (
                "docker",
                "compose",
                "--project-name",
                self.clean_project,
                "--file",
                "wiki-dev/compose.yml",
                "down",
                "--volumes",
                "--remove-orphans",
            ),
            environment=self._clean_environment,
        )

    def run(self) -> tuple[_AcceptanceSnapshot, _AcceptanceSnapshot, bool]:
        """Run both stacks, compare them, and always tear down clean resources."""
        warm_manifest_path = self.root / "wiki-dev" / "runtime" / "import_pages.manifest.json"
        warm_browser = self._validate_stack(
            base_url=self.warm_base_url,
            compose_project=self.warm_project,
            manifest_file=None,
            report_file=self.work_directory / "warm-browser.json",
        )
        warm_before = capture_acceptance(self.root, self.warm_base_url, warm_browser)
        if not warm_manifest_path.is_file():
            raise RuntimeError(f"Warm managed import manifest is missing: {warm_manifest_path}")
        warm_manifest_before = warm_manifest_path.read_bytes()

        clean_snapshot: _AcceptanceSnapshot | None = None
        primary_error: BaseException | None = None
        clean_started = False
        teardown_error: BaseException | None = None
        warm_mutation_error: BaseException | None = None
        try:
            clean_started = True
            self._bootstrap_clean_stack()
            clean_browser = self._validate_stack(
                base_url=self.clean_base_url,
                compose_project=self.clean_project,
                manifest_file=self.work_directory / "clean-import-manifest.json",
                report_file=self.work_directory / "clean-browser.json",
                initialize_cargo=True,
            )
            clean_snapshot = capture_acceptance(self.root, self.clean_base_url, clean_browser)
            differences = compare_acceptance(warm_before, clean_snapshot)
            if differences:
                rendered = "\n".join(f"- {difference}" for difference in differences)
                raise RuntimeError(f"Clean MediaWiki parity differs from warm:\n{rendered}")
        except BaseException as exc:
            primary_error = exc
        finally:
            if clean_started:
                try:
                    self._teardown_clean_stack()
                except BaseException as exc:
                    teardown_error = exc
            try:
                warm_after = capture_acceptance(self.root, self.warm_base_url, warm_browser)
                mutation_differences = compare_acceptance(warm_before, warm_after)
                manifest_changed = (
                    not warm_manifest_path.is_file() or warm_manifest_path.read_bytes() != warm_manifest_before
                )
                if mutation_differences or manifest_changed:
                    details = [*mutation_differences]
                    if manifest_changed:
                        details.append("managed import manifest bytes changed")
                    rendered = "\n".join(f"- {difference}" for difference in details)
                    warm_mutation_error = RuntimeError(f"Clean parity mutated the warm developer wiki:\n{rendered}")
            except BaseException as exc:
                warm_mutation_error = exc

        if warm_mutation_error is not None:
            raise warm_mutation_error from primary_error
        if teardown_error is not None:
            raise teardown_error from primary_error
        if primary_error is not None:
            raise primary_error
        if clean_snapshot is None:
            raise RuntimeError("Clean MediaWiki snapshot was not captured")
        return warm_before, clean_snapshot, True


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _validate_project(project: str, *, warm_project: str) -> str:
    if _PROJECT_PATTERN.fullmatch(project) is None:
        raise ValueError(f"Invalid clean Compose project name: {project!r}")
    if project == warm_project:
        raise ValueError("Clean Compose project must differ from the warm project")
    return project


def _write_report(path: Path, payload: Mapping[str, object]) -> None:
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as file:
        temporary = Path(file.name)
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--warm-base-url", default=DEFAULT_WARM_BASE_URL)
    parser.add_argument("--warm-project", default=DEFAULT_WARM_PROJECT)
    parser.add_argument("--clean-port", type=int, help="Unused host port for the clean stack")
    parser.add_argument("--clean-project", help="Unique Compose project for the clean stack")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/test-reports/wiki-clean-parity.json"),
        help="Detailed clean parity report path",
    )
    args = parser.parse_args()

    clean_port = args.clean_port if args.clean_port is not None else _available_port()
    if not 1 <= clean_port <= 65535:
        raise SystemExit(f"Invalid clean host port: {clean_port}")
    clean_project = _validate_project(
        args.clean_project or f"erenshor-wiki-clean-{uuid.uuid4().hex[:12]}",
        warm_project=args.warm_project,
    )
    clean_base_url = f"http://127.0.0.1:{clean_port}"
    report_path = args.report if args.report.is_absolute() else args.root / args.report

    with tempfile.TemporaryDirectory(prefix="erenshor-wiki-clean-") as temporary:
        harness = CleanParityHarness(
            root=args.root,
            warm_base_url=args.warm_base_url,
            warm_project=args.warm_project,
            clean_base_url=clean_base_url,
            clean_project=clean_project,
            clean_port=clean_port,
            work_directory=Path(temporary),
        )
        try:
            warm, clean, warm_unchanged = harness.run()
        except BaseException as exc:
            _write_report(
                report_path,
                {
                    "schema_version": 1,
                    "status": "failed",
                    "error": str(exc),
                    "clean_project": clean_project,
                    "clean_base_url": clean_base_url,
                    "commands": [asdict(record) for record in harness.commands],
                },
            )
            raise
        _write_report(
            report_path,
            {
                "schema_version": 1,
                "status": "passed",
                "clean_project": clean_project,
                "clean_base_url": clean_base_url,
                "warm_unchanged": warm_unchanged,
                "warm": warm.to_payload(),
                "clean": clean.to_payload(),
                "commands": [asdict(record) for record in harness.commands],
            },
        )
    print(f"PASS clean MediaWiki parity: {report_path}")


if __name__ == "__main__":
    main()

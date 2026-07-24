"""Application workflow for transactional Unity data export.

The CLI resolves configuration and owns presentation.  This module owns the
filesystem transaction and adapter sequencing so export behavior can be tested
without Unity, Typer, or a configured checkout.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from loguru import logger


class UnityExportRunner(Protocol):
    """Unity batch-mode surface required by :class:`ExportWorkflow`."""

    def execute_method(
        self,
        project_path: Path,
        class_name: str,
        method_name: str,
        log_file: Path | None = None,
        arguments: dict[str, str] | None = None,
        profile: Any | None = None,
    ) -> None: ...


ProfileImporter = Callable[[Path], None]
BackupAdapter = Callable[[Path], None]


class ExportWorkflowError(RuntimeError):
    """Raised when Unity did not produce a usable raw SQLite database."""


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """Resolved paths and options for one Unity export."""

    unity_project_dir: Path
    database_path: Path
    logs_dir: Path
    log_level: str
    profile_enabled: bool = False
    profile_output_path: Path | None = None
    profile: Any | None = None


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Observable output of a successful export."""

    database_path: Path
    log_file: Path


class ExportWorkflow:
    """Run Unity and atomically publish its raw SQLite output."""

    def __init__(
        self,
        unity_runner: UnityExportRunner,
        *,
        profile_importer: ProfileImporter | None = None,
        backup: BackupAdapter | None = None,
    ) -> None:
        self._unity_runner = unity_runner
        self._profile_importer = profile_importer
        self._backup = backup

    def run(self, request: ExportRequest) -> ExportResult:
        """Export to a sibling temporary file and publish it after validation.

        Unity, profile import, and backup failures propagate to the caller.  The
        staged file is always removed on failure, while an existing destination
        remains untouched until the final same-filesystem replacement.
        """
        request.database_path.parent.mkdir(parents=True, exist_ok=True)
        request.logs_dir.mkdir(parents=True, exist_ok=True)
        staged_path = self._make_staged_path(request.database_path)
        log_file = request.logs_dir / f"export_{int(time.time())}.log"

        try:
            logger.info(f"Exporting game data to staged raw database: {staged_path}")
            self._unity_runner.execute_method(
                project_path=request.unity_project_dir / "ExportedProject",
                class_name="ExportBatch",
                method_name="Run",
                log_file=log_file,
                arguments={
                    "dbPath": str(staged_path.absolute()),
                    "logLevel": request.log_level,
                    "profile": "true" if request.profile_enabled else "false",
                    "profileOutput": str(request.profile_output_path or ""),
                },
                profile=request.profile,
            )
            self._validate_staged_output(staged_path)

            # Keep the existing export sequence: listener rows are imported as
            # soon as Unity succeeds, before the raw file is published or backed up.
            if (
                request.profile_enabled
                and self._profile_importer is not None
                and request.profile_output_path is not None
            ):
                self._profile_importer(request.profile_output_path)

            staged_path.replace(request.database_path)
            if self._backup is not None:
                self._backup(request.database_path)
            return ExportResult(database_path=request.database_path, log_file=log_file)
        finally:
            staged_path.unlink(missing_ok=True)

    @staticmethod
    def _make_staged_path(database_path: Path) -> Path:
        fd, name = tempfile.mkstemp(
            prefix=f".{database_path.name}.",
            suffix=".tmp",
            dir=database_path.parent,
        )
        os.close(fd)
        staged_path = Path(name)
        staged_path.unlink()
        return staged_path

    @staticmethod
    def _validate_staged_output(staged_path: Path) -> None:
        if not staged_path.exists():
            raise ExportWorkflowError(f"Unity export did not produce a raw database: {staged_path}")
        if not staged_path.is_file():
            raise ExportWorkflowError(f"Unity export output is not a file: {staged_path}")
        if staged_path.stat().st_size == 0:
            raise ExportWorkflowError(f"Unity export produced an empty raw database: {staged_path}")

        try:
            with sqlite3.connect(staged_path) as connection:
                result = connection.execute("PRAGMA quick_check").fetchone()
        except sqlite3.Error as error:
            raise ExportWorkflowError(f"Unity export produced an invalid SQLite database: {staged_path}") from error
        if result != ("ok",):
            raise ExportWorkflowError(f"Unity export produced an invalid SQLite database: {staged_path}")


def adapter_exit_code(error: BaseException) -> int | None:
    """Return an adapter-provided process code without parsing log text."""
    for attribute in ("exit_code", "returncode", "return_code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    return None


__all__ = [
    "BackupAdapter",
    "ExportRequest",
    "ExportResult",
    "ExportWorkflow",
    "ExportWorkflowError",
    "ProfileImporter",
    "UnityExportRunner",
    "adapter_exit_code",
]

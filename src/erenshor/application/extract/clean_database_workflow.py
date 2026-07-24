"""Application workflow for transactional clean-database builds.

The CLI resolves variant configuration and owns presentation.  This module
owns staging, builder invocation, and publication so a failed build can never
replace a previously published clean database.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from loguru import logger

from erenshor.application.processor.build import build as build_clean_db


class CleanDatabaseBuilder(Protocol):
    """Production clean-database builder surface used by the workflow."""

    def __call__(
        self,
        *,
        raw_db_path: Path,
        clean_db_path: Path,
        mapping_json_path: Path,
    ) -> None: ...


class CleanDatabaseWorkflowError(RuntimeError):
    """Raised when a builder does not produce a publishable clean database."""


@dataclass(frozen=True, slots=True)
class CleanDatabaseRequest:
    """Resolved inputs and destination for one clean-database build."""

    raw_db_path: Path
    clean_db_path: Path
    mapping_json_path: Path


@dataclass(frozen=True, slots=True)
class CleanDatabaseResult:
    """Observable output of a successful clean-database build."""

    clean_db_path: Path


class CleanDatabaseWorkflow:
    """Build into a sibling temporary path and atomically publish the result."""

    def __init__(self, builder: CleanDatabaseBuilder = build_clean_db) -> None:
        self._builder = builder

    def run(self, request: CleanDatabaseRequest) -> CleanDatabaseResult:
        """Run the production builder and publish only a successful output.

        The existing clean database is untouched until the builder returns and
        its staged output has been validated.  Any builder or publication error
        removes the staged file and propagates to the caller.
        """
        request.clean_db_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path = self._make_staged_path(request.clean_db_path)

        try:
            logger.info(f"Building clean DB to staged path: {staged_path}")
            self._builder(
                raw_db_path=request.raw_db_path,
                clean_db_path=staged_path,
                mapping_json_path=request.mapping_json_path,
            )
            self._validate_staged_output(staged_path)
            staged_path.replace(request.clean_db_path)
            logger.info(f"Clean DB published: {request.clean_db_path}")
            return CleanDatabaseResult(clean_db_path=request.clean_db_path)
        finally:
            if staged_path.is_dir():
                shutil.rmtree(staged_path)
            else:
                staged_path.unlink(missing_ok=True)

    @staticmethod
    def _make_staged_path(clean_db_path: Path) -> Path:
        fd, name = tempfile.mkstemp(
            prefix=f".{clean_db_path.name}.",
            suffix=".tmp",
            dir=clean_db_path.parent,
        )
        os.close(fd)
        staged_path = Path(name)
        staged_path.unlink()
        return staged_path

    @staticmethod
    def _validate_staged_output(staged_path: Path) -> None:
        if not staged_path.exists():
            raise CleanDatabaseWorkflowError(f"Clean database builder did not produce an output: {staged_path}")
        if not staged_path.is_file():
            raise CleanDatabaseWorkflowError(f"Clean database builder output is not a file: {staged_path}")
        if staged_path.stat().st_size == 0:
            raise CleanDatabaseWorkflowError(f"Clean database builder produced an empty output: {staged_path}")

        try:
            with sqlite3.connect(staged_path) as connection:
                result = connection.execute("PRAGMA quick_check").fetchone()
        except sqlite3.Error as error:
            raise CleanDatabaseWorkflowError(
                f"Clean database builder produced an invalid SQLite database: {staged_path}"
            ) from error
        if result != ("ok",):
            raise CleanDatabaseWorkflowError(
                f"Clean database builder produced an invalid SQLite database: {staged_path}"
            )


__all__ = [
    "CleanDatabaseBuilder",
    "CleanDatabaseRequest",
    "CleanDatabaseResult",
    "CleanDatabaseWorkflow",
    "CleanDatabaseWorkflowError",
]

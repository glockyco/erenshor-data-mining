"""Backup service for creating per-build database and script backups.

This module provides automated backup functionality that creates uncompressed
backups of game data organized by Steam build ID. Backups are designed for
easy diffing and change tracking across game versions.

Features:
- Per-build ID backups (not timestamp-based)
- Uncompressed format for easy diffing
- Atomic operations (temp dir + rename)
- Automatic overwrite of same build
- Disk usage calculation and reporting
- Metadata tracking

The service is integrated with the export command to automatically create
backups after successful database exports.
"""

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class BackupError(Exception):
    """Base exception for backup-related errors."""

    pass


class BackupValidationError(BackupError):
    """Raised when backup validation fails."""

    pass


@dataclass
class BackupMetadata:
    """Metadata for a backup.

    This metadata is stored as JSON in each backup directory to track
    backup details and enable validation.

    Attributes:
        variant: Game variant (main, playtest, demo).
        build_id: Steam build ID.
        app_id: Steam App ID.
        created_at: ISO 8601 timestamp of backup creation.
        database_path: Name of database file in backup.
        database_size_bytes: Size of database file.
        scripts_count: Number of C# script files backed up.
        scripts_size_bytes: Total size of all script files.
        total_size_bytes: Total backup size.
    """

    variant: str
    build_id: str
    app_id: str
    created_at: str
    database_path: str
    database_size_bytes: int
    scripts_count: int
    scripts_size_bytes: int
    total_size_bytes: int


@dataclass
class BackupStats:
    """Statistics for a backup.

    Used for display and validation purposes.

    Attributes:
        build_id: Steam build ID.
        database_files: Number of database files (should be 1).
        database_size: Total database size in bytes.
        script_files: Number of C# script files.
        scripts_size: Total scripts size in bytes.
        total_size: Total backup size in bytes.
        backup_path: Path to backup directory.
    """

    build_id: str
    database_files: int
    database_size: int
    script_files: int
    scripts_size: int
    total_size: int
    backup_path: Path


class BackupService:
    """Service for creating and managing game data backups.

    This service creates uncompressed backups of database and game scripts
    organized by Steam build ID. Backups enable easy diffing and change
    tracking across game versions.

    Backup Structure:
        variants/{variant}/backups/
        ├── build-20370413/
        │   ├── metadata.json
        │   ├── database/
        │   │   └── erenshor-main.sqlite
        │   └── scripts/
        │       └── (385 .cs files)

    Key Features:
        - One backup per build ID (not timestamp)
        - Uncompressed for easy diffing
        - Atomic operations (no partial backups)
        - Automatic overwrite on same build
        - Keep all backups indefinitely
        - Disk usage reporting

    Example:
        >>> # Create backup for main variant
        >>> service = BackupService()
        >>> stats = service.create_backup(
        ...     variant="main",
        ...     build_id="20370413",
        ...     database_path=Path("variants/main/erenshor-main.sqlite"),
        ...     scripts_path=Path("variants/main/unity/Assets/Scripts"),
        ...     backup_dir=Path("variants/main/backups"),
        ...     app_id="2382520"
        ... )
        >>> print(f"Backup created: {stats.total_size} bytes")

        >>> # Show backup statistics
        >>> service.display_backup_stats(stats)
    """

    def __init__(self) -> None:
        """Initialize backup service."""
        self.console = Console()

    def create_backup(
        self,
        variant: str,
        build_id: str,
        database_path: Path,
        scripts_path: Path,
        backup_dir: Path,
        app_id: str,
    ) -> BackupStats:
        """Create backup for a specific build.

        Creates an uncompressed backup of database and game scripts. Uses
        atomic operations (temp dir + rename) to prevent partial backups.
        Automatically overwrites existing backup for same build ID.

        Args:
            variant: Game variant (main, playtest, demo).
            build_id: Steam build ID.
            database_path: Path to database file to backup.
            scripts_path: Path to game scripts directory.
            backup_dir: Base backup directory.
            app_id: Steam App ID.

        Returns:
            BackupStats with details about created backup.

        Raises:
            BackupError: If backup creation fails.
            BackupValidationError: If backup validation fails.

        Example:
            >>> service = BackupService()
            >>> stats = service.create_backup(
            ...     variant="main",
            ...     build_id="20370413",
            ...     database_path=Path("variants/main/erenshor-main.sqlite"),
            ...     scripts_path=Path("variants/main/unity/Assets/Scripts"),
            ...     backup_dir=Path("variants/main/backups"),
            ...     app_id="2382520"
            ... )
        """
        logger.info(f"Creating backup for build {build_id}")

        # Validate inputs
        if not database_path.exists():
            raise BackupError(f"Database not found: {database_path}")

        if not scripts_path.exists():
            raise BackupError(f"Scripts directory not found: {scripts_path}")

        # Prepare paths
        backup_dir.mkdir(parents=True, exist_ok=True)
        final_backup_path = backup_dir / f"build-{build_id}"
        temp_backup_path = backup_dir / f".backup-{build_id}.tmp"

        # Remove any existing temp directory (failed backup)
        if temp_backup_path.exists():
            logger.warning(f"Removing existing temp backup: {temp_backup_path}")
            shutil.rmtree(temp_backup_path)

        # Remove existing backup for same build (overwrite behavior)
        if final_backup_path.exists():
            logger.info(f"Overwriting existing backup for build {build_id}")
            shutil.rmtree(final_backup_path)

        try:
            # Create temp directory structure
            temp_backup_path.mkdir(parents=True)
            temp_db_dir = temp_backup_path / "database"
            temp_scripts_dir = temp_backup_path / "scripts"
            temp_db_dir.mkdir()
            temp_scripts_dir.mkdir()

            # Copy database
            logger.debug(f"Copying database: {database_path.name}")
            db_dest = temp_db_dir / database_path.name
            shutil.copy2(database_path, db_dest)
            db_size = db_dest.stat().st_size

            # Copy scripts directory
            logger.debug(f"Copying scripts from: {scripts_path}")
            scripts_size = 0
            scripts_count = 0

            for script_file in scripts_path.rglob("*.cs"):
                # Skip Editor scripts (our code, not game code)
                if "/Editor/" in str(script_file):
                    continue

                # Preserve directory structure
                rel_path = script_file.relative_to(scripts_path)
                dest_file = temp_scripts_dir / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(script_file, dest_file)
                scripts_size += dest_file.stat().st_size
                scripts_count += 1

            total_size = db_size + scripts_size

            # Create metadata
            metadata = BackupMetadata(
                variant=variant,
                build_id=build_id,
                app_id=app_id,
                created_at=datetime.now(UTC).isoformat(),
                database_path=database_path.name,
                database_size_bytes=db_size,
                scripts_count=scripts_count,
                scripts_size_bytes=scripts_size,
                total_size_bytes=total_size,
            )

            # Write metadata
            metadata_path = temp_backup_path / "metadata.json"
            metadata_path.write_text(json.dumps(asdict(metadata), indent=2))

            # Atomic rename (final step)
            logger.debug("Renaming temp backup to final location")
            temp_backup_path.rename(final_backup_path)

            logger.info(f"Backup created successfully: {final_backup_path}")

            # Validate backup
            self._validate_backup(final_backup_path)

            # Return stats
            return BackupStats(
                build_id=build_id,
                database_files=1,
                database_size=db_size,
                script_files=scripts_count,
                scripts_size=scripts_size,
                total_size=total_size,
                backup_path=final_backup_path,
            )

        except Exception as e:
            # Cleanup temp directory on failure
            if temp_backup_path.exists():
                logger.debug(f"Cleaning up failed backup: {temp_backup_path}")
                shutil.rmtree(temp_backup_path)

            raise BackupError(f"Backup creation failed: {e}") from e

    def _validate_backup(self, backup_path: Path) -> None:
        """Validate backup integrity.

        Performs minimal validation to ensure backup is complete:
        - Metadata file exists and is valid JSON
        - Database directory exists and contains file
        - Scripts directory exists and contains files

        Args:
            backup_path: Path to backup directory.

        Raises:
            BackupValidationError: If validation fails.
        """
        logger.debug(f"Validating backup: {backup_path}")

        # Check metadata
        metadata_path = backup_path / "metadata.json"
        if not metadata_path.exists():
            raise BackupValidationError("Metadata file missing")

        try:
            metadata_path.read_text()
        except Exception as e:
            raise BackupValidationError(f"Invalid metadata file: {e}") from e

        # Check database
        db_dir = backup_path / "database"
        if not db_dir.exists():
            raise BackupValidationError("Database directory missing")

        db_files = list(db_dir.glob("*.sqlite"))
        if not db_files:
            raise BackupValidationError("Database file missing")

        if db_files[0].stat().st_size == 0:
            raise BackupValidationError("Database file is empty")

        # Check scripts
        scripts_dir = backup_path / "scripts"
        if not scripts_dir.exists():
            raise BackupValidationError("Scripts directory missing")

        script_files = list(scripts_dir.rglob("*.cs"))
        if not script_files:
            raise BackupValidationError("No script files found")

        logger.debug(f"Backup validation passed: {len(script_files)} scripts, {len(db_files)} database")

    def display_backup_stats(self, stats: BackupStats) -> None:
        """Display backup statistics using Rich formatting.

        Shows backup details in a visually appealing format with
        human-readable file sizes.

        Args:
            stats: Backup statistics to display.

        Example:
            >>> service = BackupService()
            >>> service.display_backup_stats(stats)
            ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
            ┃          Backup Created                ┃
            ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
              Build ID: 20370413
              Database: 5.5 MB (1 file)
              Scripts:  8.5 MB (385 files)
              ────────────────────────────
              Total:    14.0 MB
        """
        # Create table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="dim")
        table.add_column("Value", style="bold")

        # Add rows
        table.add_row("Build ID:", stats.build_id)

        # Database row
        db_count = stats.database_files
        db_label = "file" if db_count == 1 else "files"
        table.add_row(
            "Database:",
            f"{self._format_size(stats.database_size)} ({db_count} {db_label})",
        )

        # Scripts row
        script_count = stats.script_files
        script_label = "file" if script_count == 1 else "files"
        table.add_row(
            "Scripts:",
            f"{self._format_size(stats.scripts_size)} ({script_count} {script_label})",
        )
        table.add_row("─" * 30, "─" * 30)
        table.add_row("Total:", f"{self._format_size(stats.total_size)}")
        table.add_row("", "")
        table.add_row("Location:", str(stats.backup_path))

        # Display in panel
        self.console.print()
        self.console.print(
            Panel(
                table,
                title="Backup Created",
                border_style="green",
            )
        )
        self.console.print()

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size as human-readable string.

        Args:
            size_bytes: Size in bytes.

        Returns:
            Formatted string (e.g., "5.5 MB", "8.5 KB").

        Example:
            >>> service = BackupService()
            >>> service._format_size(1024)
            "1.0 KB"
            >>> service._format_size(1048576)
            "1.0 MB"
            >>> service._format_size(500)
            "500 bytes"
        """
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def get_existing_backup(self, backup_dir: Path, build_id: str) -> Path | None:
        """Get path to existing backup for build ID.

        Args:
            backup_dir: Base backup directory.
            build_id: Steam build ID.

        Returns:
            Path to backup directory if exists, None otherwise.

        Example:
            >>> service = BackupService()
            >>> backup = service.get_existing_backup(
            ...     backup_dir=Path("variants/main/backups"),
            ...     build_id="20370413"
            ... )
            >>> if backup:
            ...     print(f"Found existing backup: {backup}")
        """
        backup_path = backup_dir / f"build-{build_id}"
        return backup_path if backup_path.exists() else None

    def list_backups(self, backup_dir: Path) -> list[BackupMetadata]:
        """List all backups in directory.

        Reads metadata from all backup directories and returns as list.
        Skips directories without valid metadata.

        Args:
            backup_dir: Base backup directory.

        Returns:
            List of BackupMetadata, sorted by build ID (newest first).

        Example:
            >>> service = BackupService()
            >>> backups = service.list_backups(Path("variants/main/backups"))
            >>> for backup in backups:
            ...     print(f"Build {backup.build_id}: {backup.created_at}")
        """
        if not backup_dir.exists():
            return []

        backups = []

        for backup_path in backup_dir.iterdir():
            if not backup_path.is_dir():
                continue

            # Skip temp directories
            if backup_path.name.startswith(".backup-"):
                continue

            # Read metadata
            metadata_path = backup_path / "metadata.json"
            if not metadata_path.exists():
                logger.warning(f"Skipping backup without metadata: {backup_path}")
                continue

            try:
                metadata_dict = json.loads(metadata_path.read_text())
                metadata = BackupMetadata(**metadata_dict)
                backups.append(metadata)
            except Exception as e:
                logger.warning(f"Failed to read backup metadata: {backup_path} - {e}")
                continue

        # Sort by build ID (descending - newest first)
        backups.sort(key=lambda b: b.build_id, reverse=True)

        return backups

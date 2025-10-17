"""Tests for BackupService."""

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from erenshor.application.services import (
    BackupError,
    BackupService,
    BackupValidationError,
)


class TestBackupService:
    """Test suite for BackupService."""

    @pytest.fixture
    def backup_service(self) -> BackupService:
        """Create BackupService instance."""
        return BackupService()

    @pytest.fixture
    def mock_database(self, tmp_path: Path) -> Path:
        """Create mock database file."""
        db_path = tmp_path / "erenshor-main.sqlite"
        # Create 5 MB database
        db_path.write_bytes(b"x" * (5 * 1024 * 1024))
        return db_path

    @pytest.fixture
    def mock_scripts(self, tmp_path: Path) -> Path:
        """Create mock scripts directory."""
        scripts_path = tmp_path / "scripts"
        scripts_path.mkdir()

        # Create some test scripts
        (scripts_path / "GameManager.cs").write_text("// Game manager script")
        (scripts_path / "Player.cs").write_text("// Player script")
        (scripts_path / "Enemy.cs").write_text("// Enemy script")

        # Create subdirectory
        subdir = scripts_path / "UI"
        subdir.mkdir()
        (subdir / "Menu.cs").write_text("// Menu script")

        return scripts_path

    def test_create_backup_success(
        self,
        backup_service: BackupService,
        mock_database: Path,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test successful backup creation."""
        backup_dir = tmp_path / "backups"
        build_id = "20370413"

        stats = backup_service.create_backup(
            variant="main",
            build_id=build_id,
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Verify stats
        assert stats.build_id == build_id
        assert stats.database_files == 1
        assert stats.database_size > 0
        assert stats.script_files == 4  # 4 .cs files
        assert stats.scripts_size > 0
        assert stats.total_size == stats.database_size + stats.scripts_size

        # Verify backup directory exists
        backup_path = backup_dir / f"build-{build_id}"
        assert backup_path.exists()
        assert backup_path.is_dir()

        # Verify structure
        assert (backup_path / "metadata.json").exists()
        assert (backup_path / "database").exists()
        assert (backup_path / "scripts").exists()

        # Verify database copied
        db_files = list((backup_path / "database").glob("*.sqlite"))
        assert len(db_files) == 1
        assert db_files[0].stat().st_size == mock_database.stat().st_size

        # Verify scripts copied
        script_files = list((backup_path / "scripts").rglob("*.cs"))
        assert len(script_files) == 4

        # Verify subdirectory structure preserved
        assert (backup_path / "scripts" / "UI" / "Menu.cs").exists()

    def test_create_backup_metadata(
        self,
        backup_service: BackupService,
        mock_database: Path,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test backup metadata is created correctly."""
        backup_dir = tmp_path / "backups"
        build_id = "20370413"

        backup_service.create_backup(
            variant="main",
            build_id=build_id,
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Read metadata
        backup_path = backup_dir / f"build-{build_id}"
        metadata_path = backup_path / "metadata.json"
        metadata = json.loads(metadata_path.read_text())

        # Verify metadata fields
        assert metadata["variant"] == "main"
        assert metadata["build_id"] == build_id
        assert metadata["app_id"] == "2382520"
        assert metadata["database_path"] == mock_database.name
        assert metadata["database_size_bytes"] > 0
        assert metadata["scripts_count"] == 4
        assert metadata["scripts_size_bytes"] > 0
        assert metadata["total_size_bytes"] > 0

        # Verify timestamp is valid ISO 8601
        created_at = datetime.fromisoformat(metadata["created_at"])
        assert created_at.tzinfo == UTC

    def test_create_backup_overwrites_existing(
        self,
        backup_service: BackupService,
        mock_database: Path,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test that creating backup for same build ID overwrites existing."""
        backup_dir = tmp_path / "backups"
        build_id = "20370413"

        # Create first backup
        backup_service.create_backup(
            variant="main",
            build_id=build_id,
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Get first backup creation time
        backup_path = backup_dir / f"build-{build_id}"
        metadata1 = json.loads((backup_path / "metadata.json").read_text())
        created_at1 = metadata1["created_at"]

        # Create second backup (should overwrite)
        backup_service.create_backup(
            variant="main",
            build_id=build_id,
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Get second backup creation time
        metadata2 = json.loads((backup_path / "metadata.json").read_text())
        created_at2 = metadata2["created_at"]

        # Verify overwrite happened (different timestamps)
        assert created_at1 != created_at2

        # Verify only one backup exists
        backups = list(backup_dir.glob("build-*"))
        assert len(backups) == 1

    def test_create_backup_different_builds(
        self,
        backup_service: BackupService,
        mock_database: Path,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test that different build IDs create separate backups."""
        backup_dir = tmp_path / "backups"

        # Create backup for build 1
        backup_service.create_backup(
            variant="main",
            build_id="20370413",
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Create backup for build 2
        backup_service.create_backup(
            variant="main",
            build_id="20370414",
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Verify both backups exist
        backups = sorted(backup_dir.glob("build-*"))
        assert len(backups) == 2
        assert backups[0].name == "build-20370413"
        assert backups[1].name == "build-20370414"

    def test_create_backup_database_not_found(
        self,
        backup_service: BackupService,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test error when database file doesn't exist."""
        backup_dir = tmp_path / "backups"
        missing_db = tmp_path / "missing.sqlite"

        with pytest.raises(BackupError, match="Database not found"):
            backup_service.create_backup(
                variant="main",
                build_id="20370413",
                database_path=missing_db,
                scripts_path=mock_scripts,
                backup_dir=backup_dir,
                app_id="2382520",
            )

    def test_create_backup_scripts_not_found(
        self,
        backup_service: BackupService,
        mock_database: Path,
        tmp_path: Path,
    ):
        """Test error when scripts directory doesn't exist."""
        backup_dir = tmp_path / "backups"
        missing_scripts = tmp_path / "missing_scripts"

        with pytest.raises(BackupError, match="Scripts directory not found"):
            backup_service.create_backup(
                variant="main",
                build_id="20370413",
                database_path=mock_database,
                scripts_path=missing_scripts,
                backup_dir=backup_dir,
                app_id="2382520",
            )

    def test_create_backup_atomic_on_failure(
        self,
        backup_service: BackupService,
        mock_database: Path,
        tmp_path: Path,
    ):
        """Test that failed backup doesn't leave partial backup."""
        backup_dir = tmp_path / "backups"
        build_id = "20370413"

        # Create scripts directory that will cause failure
        scripts_path = tmp_path / "scripts"
        scripts_path.mkdir()
        # Add a file that will cause copy to fail (simulate permission error)
        # We'll just use a non-existent subdirectory as scripts_path
        bad_scripts = tmp_path / "nonexistent"

        with contextlib.suppress(BackupError):
            backup_service.create_backup(
                variant="main",
                build_id=build_id,
                database_path=mock_database,
                scripts_path=bad_scripts,
                backup_dir=backup_dir,
                app_id="2382520",
            )

        # Verify no backup directory exists
        backup_path = backup_dir / f"build-{build_id}"
        assert not backup_path.exists()

        # Verify no temp directory left behind
        temp_path = backup_dir / f".backup-{build_id}.tmp"
        assert not temp_path.exists()

    def test_create_backup_skips_editor_scripts(
        self,
        backup_service: BackupService,
        mock_database: Path,
        tmp_path: Path,
    ):
        """Test that Editor scripts are excluded from backup."""
        # Create scripts with Editor subdirectory
        scripts_path = tmp_path / "scripts"
        scripts_path.mkdir()

        # Game scripts
        (scripts_path / "Game.cs").write_text("// Game script")

        # Editor scripts (should be skipped)
        editor_dir = scripts_path / "Editor"
        editor_dir.mkdir()
        (editor_dir / "EditorScript.cs").write_text("// Editor script")

        backup_dir = tmp_path / "backups"
        build_id = "20370413"

        stats = backup_service.create_backup(
            variant="main",
            build_id=build_id,
            database_path=mock_database,
            scripts_path=scripts_path,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Verify only game script was backed up (not editor script)
        assert stats.script_files == 1

        backup_path = backup_dir / f"build-{build_id}"
        script_files = list((backup_path / "scripts").rglob("*.cs"))
        assert len(script_files) == 1
        assert script_files[0].name == "Game.cs"

    def test_get_existing_backup(
        self,
        backup_service: BackupService,
        mock_database: Path,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test getting existing backup by build ID."""
        backup_dir = tmp_path / "backups"
        build_id = "20370413"

        # No backup exists yet
        backup = backup_service.get_existing_backup(backup_dir, build_id)
        assert backup is None

        # Create backup
        backup_service.create_backup(
            variant="main",
            build_id=build_id,
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        # Now backup should exist
        backup = backup_service.get_existing_backup(backup_dir, build_id)
        assert backup is not None
        assert backup.name == f"build-{build_id}"

    def test_list_backups_empty(
        self,
        backup_service: BackupService,
        tmp_path: Path,
    ):
        """Test listing backups when directory is empty."""
        backup_dir = tmp_path / "backups"

        # Directory doesn't exist yet
        backups = backup_service.list_backups(backup_dir)
        assert backups == []

        # Directory exists but empty
        backup_dir.mkdir()
        backups = backup_service.list_backups(backup_dir)
        assert backups == []

    def test_list_backups_multiple(
        self,
        backup_service: BackupService,
        mock_database: Path,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test listing multiple backups."""
        backup_dir = tmp_path / "backups"

        # Create multiple backups
        builds = ["20370413", "20370414", "20370415"]
        for build_id in builds:
            backup_service.create_backup(
                variant="main",
                build_id=build_id,
                database_path=mock_database,
                scripts_path=mock_scripts,
                backup_dir=backup_dir,
                app_id="2382520",
            )

        # List backups
        backups = backup_service.list_backups(backup_dir)
        assert len(backups) == 3

        # Verify sorted by build ID (descending)
        assert backups[0].build_id == "20370415"
        assert backups[1].build_id == "20370414"
        assert backups[2].build_id == "20370413"

    def test_list_backups_skips_temp(
        self,
        backup_service: BackupService,
        tmp_path: Path,
    ):
        """Test that list_backups skips temp directories."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create a temp directory (simulating failed backup)
        temp_dir = backup_dir / ".backup-20370413.tmp"
        temp_dir.mkdir()
        (temp_dir / "metadata.json").write_text("{}")

        # List should be empty
        backups = backup_service.list_backups(backup_dir)
        assert backups == []

    def test_list_backups_skips_invalid_metadata(
        self,
        backup_service: BackupService,
        tmp_path: Path,
    ):
        """Test that list_backups skips backups with invalid metadata."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create backup with invalid metadata
        invalid_backup = backup_dir / "build-20370413"
        invalid_backup.mkdir()
        (invalid_backup / "metadata.json").write_text("invalid json")

        # List should be empty (invalid backup skipped)
        backups = backup_service.list_backups(backup_dir)
        assert backups == []

    def test_format_size(self, backup_service: BackupService):
        """Test human-readable size formatting."""
        assert backup_service._format_size(500) == "500 bytes"
        assert backup_service._format_size(1024) == "1.0 KB"
        assert backup_service._format_size(1536) == "1.5 KB"
        assert backup_service._format_size(1048576) == "1.0 MB"
        assert backup_service._format_size(5242880) == "5.0 MB"
        assert backup_service._format_size(1073741824) == "1.0 GB"

    def test_validate_backup_success(
        self,
        backup_service: BackupService,
        mock_database: Path,
        mock_scripts: Path,
        tmp_path: Path,
    ):
        """Test backup validation succeeds for valid backup."""
        backup_dir = tmp_path / "backups"
        build_id = "20370413"

        backup_service.create_backup(
            variant="main",
            build_id=build_id,
            database_path=mock_database,
            scripts_path=mock_scripts,
            backup_dir=backup_dir,
            app_id="2382520",
        )

        backup_path = backup_dir / f"build-{build_id}"

        # Should not raise
        backup_service._validate_backup(backup_path)

    def test_validate_backup_missing_metadata(
        self,
        backup_service: BackupService,
        tmp_path: Path,
    ):
        """Test validation fails when metadata is missing."""
        backup_path = tmp_path / "backup"
        backup_path.mkdir()

        with pytest.raises(BackupValidationError, match="Metadata file missing"):
            backup_service._validate_backup(backup_path)

    def test_validate_backup_empty_database(
        self,
        backup_service: BackupService,
        tmp_path: Path,
    ):
        """Test validation fails when database is empty."""
        backup_path = tmp_path / "backup"
        backup_path.mkdir()

        # Create metadata
        (backup_path / "metadata.json").write_text("{}")

        # Create empty database
        db_dir = backup_path / "database"
        db_dir.mkdir()
        (db_dir / "erenshor.sqlite").write_text("")  # Empty file

        # Create scripts
        scripts_dir = backup_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "test.cs").write_text("// test")

        with pytest.raises(BackupValidationError, match="Database file is empty"):
            backup_service._validate_backup(backup_path)

    def test_validate_backup_no_scripts(
        self,
        backup_service: BackupService,
        tmp_path: Path,
    ):
        """Test validation fails when no scripts found."""
        backup_path = tmp_path / "backup"
        backup_path.mkdir()

        # Create metadata
        (backup_path / "metadata.json").write_text("{}")

        # Create database
        db_dir = backup_path / "database"
        db_dir.mkdir()
        (db_dir / "erenshor.sqlite").write_bytes(b"x" * 1024)

        # Create empty scripts directory
        scripts_dir = backup_path / "scripts"
        scripts_dir.mkdir()

        with pytest.raises(BackupValidationError, match="No script files found"):
            backup_service._validate_backup(backup_path)

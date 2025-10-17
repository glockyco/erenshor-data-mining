"""Tests for Steam/game file precondition checks."""

from pathlib import Path

from erenshor.cli.preconditions.checks.steam import game_files_exist, steam_credentials_exist


def test_game_files_exist_with_files_present(tmp_path: Path):
    """Test game_files_exist passes when game directory has files."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "game.exe").write_text("game")
    (game_dir / "data").mkdir()

    context = {"game_dir": game_dir}
    result = game_files_exist(context)

    assert result.passed is True
    assert "present" in result.message.lower()


def test_game_files_exist_when_directory_missing(tmp_path: Path):
    """Test game_files_exist fails when directory doesn't exist."""
    game_dir = tmp_path / "nonexistent"

    context = {"game_dir": game_dir}
    result = game_files_exist(context)

    assert result.passed is False
    assert "not found" in result.message.lower()


def test_game_files_exist_when_directory_empty(tmp_path: Path):
    """Test game_files_exist fails when directory is empty."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    context = {"game_dir": game_dir}
    result = game_files_exist(context)

    assert result.passed is False
    assert "empty" in result.message.lower()


def test_game_files_exist_when_path_is_file(tmp_path: Path):
    """Test game_files_exist fails when path is a file."""
    game_file = tmp_path / "game.txt"
    game_file.write_text("not a directory")

    context = {"game_dir": game_file}
    result = game_files_exist(context)

    assert result.passed is False
    assert "not a directory" in result.message.lower()


def test_steam_credentials_exist_with_both_set(monkeypatch):
    """Test steam_credentials_exist passes when both credentials are set."""
    monkeypatch.setenv("STEAM_USERNAME", "testuser")
    monkeypatch.setenv("STEAM_PASSWORD", "testpass")

    context = {}
    result = steam_credentials_exist(context)

    assert result.passed is True
    assert "configured" in result.message.lower()
    # Should preview username but not expose full credentials
    assert "tes***" in result.message


def test_steam_credentials_exist_without_username(monkeypatch):
    """Test steam_credentials_exist fails when username is missing."""
    monkeypatch.delenv("STEAM_USERNAME", raising=False)
    monkeypatch.setenv("STEAM_PASSWORD", "testpass")

    context = {}
    result = steam_credentials_exist(context)

    assert result.passed is False
    assert "not configured" in result.message.lower()
    assert "STEAM_USERNAME" in result.detail


def test_steam_credentials_exist_without_password(monkeypatch):
    """Test steam_credentials_exist fails when password is missing."""
    monkeypatch.setenv("STEAM_USERNAME", "testuser")
    monkeypatch.delenv("STEAM_PASSWORD", raising=False)

    context = {}
    result = steam_credentials_exist(context)

    assert result.passed is False
    assert "incomplete" in result.message.lower()
    assert "STEAM_PASSWORD" in result.detail


def test_steam_credentials_exist_with_neither_set(monkeypatch):
    """Test steam_credentials_exist fails when neither credential is set."""
    monkeypatch.delenv("STEAM_USERNAME", raising=False)
    monkeypatch.delenv("STEAM_PASSWORD", raising=False)

    context = {}
    result = steam_credentials_exist(context)

    assert result.passed is False
    assert "not configured" in result.message.lower()


def test_steam_credentials_preview_short_username(monkeypatch):
    """Test steam_credentials_exist handles short usernames safely."""
    monkeypatch.setenv("STEAM_USERNAME", "ab")  # Short username
    monkeypatch.setenv("STEAM_PASSWORD", "testpass")

    context = {}
    result = steam_credentials_exist(context)

    assert result.passed is True
    # Should not expose short username
    assert "***" in result.message

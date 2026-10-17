from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import typer

from erenshor.cli.main import main


def _config(default_variant: str) -> SimpleNamespace:
    return SimpleNamespace(
        default_variant=default_variant,
        variants={"main": object(), "playtest": object()},
        global_=SimpleNamespace(logging=SimpleNamespace(level="info")),
    )


def _context() -> Mock:
    context = Mock(spec=typer.Context)
    context.obj = None
    return context


def test_omitted_variant_uses_config_default() -> None:
    context = _context()
    config = _config("playtest")

    with (
        patch("erenshor.cli.main.load_config", return_value=config),
        patch("erenshor.cli.main.get_repo_root", return_value=Path("/repo")),
        patch("erenshor.cli.main.setup_logging"),
    ):
        main(context, variant=None, dry_run=False, verbose=False, quiet=False)

    assert context.obj.variant == "playtest"


def test_explicit_variant_wins_over_config_default() -> None:
    context = _context()
    config = _config("playtest")

    with (
        patch("erenshor.cli.main.load_config", return_value=config),
        patch("erenshor.cli.main.get_repo_root", return_value=Path("/repo")),
        patch("erenshor.cli.main.setup_logging"),
    ):
        main(context, variant="main", dry_run=False, verbose=False, quiet=False)

    assert context.obj.variant == "main"


@pytest.mark.parametrize("variant", [None, "missing"])
def test_invalid_variant_fails_before_logging_setup(
    variant: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    context = _context()
    config = _config("missing")
    setup_logging = Mock()

    with (
        patch("erenshor.cli.main.load_config", return_value=config),
        patch("erenshor.cli.main.get_repo_root", return_value=Path("/repo")),
        patch("erenshor.cli.main.setup_logging", setup_logging),
        pytest.raises(typer.Exit),
    ):
        main(context, variant=variant, dry_run=False, verbose=False, quiet=False)

    setup_logging.assert_not_called()
    assert context.obj is None
    stderr = capsys.readouterr().err
    assert "Configuration Error: Unknown variant 'missing'" in stderr
    assert "Unexpected error" not in stderr


def test_source_checkout_mismatch_fails_before_config_loading_and_logging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: ../main/.git/worktrees/test")
    source = tmp_path / "main"
    source.mkdir()
    (source / ".git").mkdir()
    monkeypatch.setattr("erenshor.__file__", str(source / "src/erenshor/__init__.py"))
    context = _context()
    with (
        patch("erenshor.cli.main.get_repo_root", return_value=root),
        patch("erenshor.cli.main.load_config") as load_config,
        patch("erenshor.cli.main.setup_logging") as setup_logging,
        pytest.raises(typer.Exit) as error,
    ):
        main(context, variant=None, dry_run=False, verbose=False, quiet=False)

    assert error.value.exit_code == 1
    load_config.assert_not_called()
    setup_logging.assert_not_called()
    assert context.obj is None
    stderr = capsys.readouterr().err
    assert "Imported Erenshor source belongs to" in stderr
    assert "Refresh the dev shell" in stderr
    assert "Unexpected error" not in stderr

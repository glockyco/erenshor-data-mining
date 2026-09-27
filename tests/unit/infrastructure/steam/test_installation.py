"""Discovery of a variant's CrossOver Steam client installation."""

from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.infrastructure.steam import installation
from erenshor.infrastructure.steam.installation import GameInstallationError, find_game_installation

MANIFEST = '"AppState"\n{\n\t"appid"\t\t"2382520"\n\t"installdir"\t\t"Erenshor"\n\t"buildid"\t\t"24405256"\n}\n'


@pytest.fixture
def bottles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "Bottles"
    root.mkdir()
    monkeypatch.setattr(installation, "CROSSOVER_BOTTLES_ROOT", root)
    monkeypatch.setattr(installation.sys, "platform", "darwin")
    monkeypatch.delenv("CROSSOVER_BOTTLE", raising=False)
    return root


def _install(
    bottles: Path, bottle: str, *, app_id: str = "2382520", manifest: str | None = MANIFEST, managed: bool = True
) -> Path:
    steamapps = bottles / bottle / "drive_c/Program Files (x86)/Steam/steamapps"
    game = steamapps / "common" / "Erenshor"
    game.mkdir(parents=True)
    if managed:
        (game / "Erenshor_Data" / "Managed").mkdir(parents=True)
    if manifest is not None:
        (steamapps / f"appmanifest_{app_id}.acf").write_text(manifest)
    return game


@pytest.mark.parametrize(
    ("variant", "app_id", "install_dir"),
    [("main", "2382520", "Erenshor"), ("playtest", "3090030", "Erenshor Playtest"), ("demo", "2522260", "Demo")],
)
def test_each_variant_resolves_to_the_installation_its_manifest_names(
    bottles: Path, variant: str, app_id: str, install_dir: str
) -> None:
    manifest = f'"AppState"\n{{\n\t"installdir"\t\t"{install_dir}"\n}}\n'
    steamapps = bottles / "Steam" / "drive_c/Program Files (x86)/Steam/steamapps"
    game = steamapps / "common" / install_dir
    (game / "Erenshor_Data" / "Managed").mkdir(parents=True)
    (steamapps / f"appmanifest_{app_id}.acf").write_text(manifest)

    found = find_game_installation(variant, app_id)

    assert found.path == game
    assert found.manifest == steamapps / f"appmanifest_{app_id}.acf"
    assert found.bottle == "Steam"


def test_absence_names_the_variant_its_app_id_and_the_steam_client(bottles: Path) -> None:
    _install(bottles, "Steam", app_id="2382520")

    with pytest.raises(GameInstallationError) as error:
        find_game_installation("demo", "2522260")

    message = str(error.value)
    assert "'demo'" in message
    assert "2522260" in message
    assert "not installed" in message
    assert "Steam client" in message


def test_ambiguity_names_every_candidate(bottles: Path) -> None:
    first = _install(bottles, "Steam")
    second = _install(bottles, "Steam Copy")

    with pytest.raises(GameInstallationError, match="several CrossOver bottles") as error:
        find_game_installation("main", "2382520")

    assert str(first) in str(error.value)
    assert str(second) in str(error.value)


def test_unusable_manifest_is_named_instead_of_reported_absent(bottles: Path) -> None:
    _install(bottles, "Steam", manifest='"AppState"\n{\n}\n')

    with pytest.raises(GameInstallationError, match=r"appmanifest_2382520\.acf") as error:
        find_game_installation("main", "2382520")

    assert "not installed" not in str(error.value)


def test_installation_without_managed_assemblies_is_rejected(bottles: Path) -> None:
    game = _install(bottles, "Steam", managed=False)

    with pytest.raises(GameInstallationError, match="without its managed assemblies") as error:
        find_game_installation("main", "2382520")

    assert str(game / "Erenshor_Data" / "Managed") in str(error.value)


def test_selected_bottle_limits_the_search(bottles: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(bottles, "Steam")
    chosen = _install(bottles, "Steam Copy")
    monkeypatch.setenv("CROSSOVER_BOTTLE", "Steam Copy")

    assert find_game_installation("main", "2382520").path == chosen

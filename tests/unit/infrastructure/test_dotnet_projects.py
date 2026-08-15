from pathlib import Path

from erenshor.infrastructure.dotnet_projects import MAINTAINED_DOTNET_RESTORE_TARGETS

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_inventory_covers_every_maintained_dotnet_project() -> None:
    inventoried = {target.project for target in MAINTAINED_DOTNET_RESTORE_TARGETS}
    discovered = {
        path.relative_to(REPO_ROOT).as_posix()
        for root in (REPO_ROOT / "src/mods", REPO_ROOT / "src/tools")
        for path in root.rglob("*.csproj")
        if "obj" not in path.parts and "bin" not in path.parts
    }

    assert inventoried == discovered


def test_inventory_names_each_restore_graph_and_lock() -> None:
    identities = {(target.project, target.properties) for target in MAINTAINED_DOTNET_RESTORE_TARGETS}

    assert len(identities) == len(MAINTAINED_DOTNET_RESTORE_TARGETS)
    for target in MAINTAINED_DOTNET_RESTORE_TARGETS:
        assert (REPO_ROOT / target.project).is_file()
        if target.lock_file is not None:
            assert (REPO_ROOT / target.lock_file).is_file()


def test_only_package_free_fixture_omits_a_lock() -> None:
    unlocked = [target.project for target in MAINTAINED_DOTNET_RESTORE_TARGETS if target.lock_file is None]

    assert unlocked == ["src/tools/CodeFacts/tests/FixtureLib/FixtureLib.csproj"]

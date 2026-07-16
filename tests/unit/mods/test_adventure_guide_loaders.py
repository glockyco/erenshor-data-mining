import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MOD_ROOT = REPO_ROOT / "src" / "mods" / "AdventureGuide"


def test_native_entrypoints_hide_their_game_objects_before_startup() -> None:
    for loader in ("BepInEx", "Lunaris"):
        source = (MOD_ROOT / "src" / f"Plugin.{loader}.cs").read_text()
        awake = source.split("private void Awake()", 1)[1]
        body = awake.split("}", 1)[0]
        assert body.index("gameObject.hideFlags = HideFlags.HideAndDontSave;") < body.index("new AdventureGuideRuntime")


def test_shared_runtime_owns_lifecycle_and_loader_neutral_contracts() -> None:
    runtime = (MOD_ROOT / "src" / "Plugin.cs").read_text()
    contracts = (MOD_ROOT / "src" / "Config" / "LoaderContracts.cs").read_text()

    assert "public AdventureGuideRuntime(IModLogger logger, IGuideConfigBackend config, string iniPath)" in runtime
    assert "public bool Start()" in runtime
    assert "public void Tick()" in runtime
    assert "public void Draw()" in runtime
    assert "if (_stopped)" in runtime
    assert "public void Stop()" in runtime
    assert "interface IConfigValue<T>" in contracts
    assert "interface IGuideConfigBackend" in contracts
    assert "event EventHandler? SettingChanged" in contracts
    assert re.search(r"interface\s+IConfigValue\s*<\s*T\s*>\s*:\s*[^\{]*\bIDisposable\b", contracts)
    assert re.search(r"interface\s+IGuideConfigBackend\s*:\s*[^\{]*\bIDisposable\b", contracts)


def test_config_keys_remain_owned_by_guide_config() -> None:
    config = (MOD_ROOT / "src" / "Config" / "GuideConfig.cs").read_text()
    assert "public GuideConfig(IGuideConfigBackend backend)" in config
    assert "KeyCode.L" in config
    assert "KeyCode.K" in config
    assert "KeyCode.P" in config
    assert "new GuideConfigEntry" not in config
    assert "using Lunaris" not in config

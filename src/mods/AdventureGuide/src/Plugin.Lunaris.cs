using ErenshorMods.Input;
using Lunaris;
using UnityEngine;

namespace AdventureGuide;

[LunarisPlugin(
    "Adventure Guide",
    PluginInfo.Version,
    "WoW_Much",
    "In-game quest guide for Erenshor."
)]
[LunarisPermission(
    LunarisPermission.FileAccess
        | LunarisPermission.Reflection
        | LunarisPermission.Harmony
        | LunarisPermission.LunarisPlugin
)]
public sealed class Plugin : LunarisPlugin
{
    private AdventureGuideRuntime? _runtime;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        var logger = new LunarisLogger(Logging);
        var config = new LunarisConfigBackend(Config);
        var iniPath = System.IO.Path.Combine(
            System.IO.Directory.GetCurrentDirectory(),
            "plugins",
            "config",
            "adventureguide",
            "imgui.ini"
        );
        _runtime = new AdventureGuideRuntime(logger, config, iniPath, UnityKeyboardInput.Instance);
        _runtime.Start();
    }

    private void Update() => _runtime?.Tick();

    private void OnGUI() => _runtime?.Draw();

    private void OnDestroy() => _runtime?.Stop();
}

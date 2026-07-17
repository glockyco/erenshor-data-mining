using BepInEx;
using ErenshorMods.Input;
using UnityEngine;

namespace AdventureGuide;

[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    private AdventureGuideRuntime? _runtime;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        var logger = new BepInExLogger(Logger);
        var config = new BepInExConfigBackend(Config);
        var iniPath = System.IO.Path.Combine(Paths.ConfigPath, "adventureguide", "imgui.ini");
        _runtime = new AdventureGuideRuntime(logger, config, iniPath, UnityKeyboardInput.Instance);
        _runtime.Start();
    }

    private void Update() => _runtime?.Tick();

    private void OnGUI() => _runtime?.Draw();

    private void OnDestroy() => _runtime?.Stop();
}

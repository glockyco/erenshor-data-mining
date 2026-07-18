using ErenshorMods.Input;
using Lunaris;
using Sprint.Config;
using Sprint.Core;
using UnityEngine;

namespace Sprint;

/// <summary>Native Lunaris adapter for the shared sprint lifecycle.</summary>
[LunarisPlugin("Sprint", PluginInfo.Version, "WoW_Much", "Configurable sprinting for Erenshor.")]
[LunarisPermission(
    LunarisPermission.Harmony | LunarisPermission.Reflection | LunarisPermission.LunarisPlugin
)]
public sealed class Plugin : LunarisPlugin
{
    private SprintSettings _settings = null!;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        _settings = Config.Register<SprintSettings>().Get();
        SprintRuntime.Start(_settings);

        Logging.LogInfo(
            $"{PluginInfo.Name} v{PluginInfo.Version} loaded\n"
                + $"  Sprint Key: {_settings.SprintKey}\n"
                + $"  Toggle Mode: {(_settings.ToggleMode ? "Enabled" : "Disabled")}\n"
                + $"  Speed Multiplier: {_settings.SprintMultiplier}x"
        );
    }

    private void Update() =>
        SprintRuntime.Tick(
            KeyboardShortcuts.IsHeld(_settings.SprintKey, UnityKeyboardInput.Instance)
        );

    private void OnDestroy() => SprintRuntime.Stop();
}

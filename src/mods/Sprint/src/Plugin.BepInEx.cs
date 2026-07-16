using BepInEx;
using BepInEx.Configuration;
using Sprint.Config;
using Sprint.Core;
using UnityEngine;

namespace Sprint;

/// <summary>Native BepInEx adapter for the shared sprint lifecycle.</summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    private ConfigEntry<bool> _enabled = null!;
    private ConfigEntry<KeyboardShortcut> _sprintKey = null!;
    private ConfigEntry<bool> _toggleMode = null!;
    private ConfigEntry<float> _sprintMultiplier = null!;
    private BepSprintSettings _settings = null!;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        _enabled = Config.Bind(
            "General",
            "Enabled",
            true,
            "Master switch. When false, sprint is disabled."
        );
        _sprintKey = Config.Bind(
            "Controls",
            "SprintKey",
            new KeyboardShortcut(KeyCode.LeftShift),
            "Controls sprinting. Hold it, or tap to toggle when Toggle Mode is enabled."
        );
        _toggleMode = Config.Bind(
            "Controls",
            "ToggleMode",
            false,
            "If true, tap sprint key to toggle sprint on/off. If false, hold it to sprint."
        );
        _sprintMultiplier = Config.Bind(
            "Settings",
            "SprintMultiplier",
            1.5f,
            new ConfigDescription(
                "Speed multiplier when sprinting. 1.5 = 50% faster, 2.0 = 100% faster.",
                new AcceptableValueRange<float>(1f, 10f)
            )
        );

        _settings = new BepSprintSettings(_enabled, _toggleMode, _sprintMultiplier);
        SprintRuntime.Start(_settings, () => _sprintKey.Value.IsPressed());

        Logger.LogInfo(
            $"{PluginInfo.Name} v{PluginInfo.Version} loaded\n"
                + $"  Sprint Key: {_sprintKey.Value}\n"
                + $"  Toggle Mode: {(_toggleMode.Value ? "Enabled" : "Disabled")}\n"
                + $"  Speed Multiplier: {_sprintMultiplier.Value}x"
        );
    }

    private void Update() => SprintRuntime.Tick();

    private void OnDestroy() => SprintRuntime.Stop();

    private sealed class BepSprintSettings : ISprintSettings
    {
        private readonly ConfigEntry<bool> _enabled;
        private readonly ConfigEntry<bool> _toggleMode;
        private readonly ConfigEntry<float> _multiplier;

        internal BepSprintSettings(
            ConfigEntry<bool> enabled,
            ConfigEntry<bool> toggleMode,
            ConfigEntry<float> multiplier
        )
        {
            _enabled = enabled;
            _toggleMode = toggleMode;
            _multiplier = multiplier;
        }

        public bool Enabled => _enabled.Value;

        public bool ToggleMode => _toggleMode.Value;

        public float Multiplier => _multiplier.Value;
    }
}

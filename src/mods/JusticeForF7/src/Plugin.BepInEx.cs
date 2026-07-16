using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using UnityEngine;

namespace JusticeForF7;

/// <summary>Native BepInEx entry point for Justice for F7.</summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    private JusticeRuntime? _runtime;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        var settings = new BepInExJusticeSettings(Config);
        _runtime = new JusticeRuntime(new BepInExModLogger(Logger), settings);
        _runtime.Start();
    }

    private void Update()
    {
        _runtime?.Tick();
    }

    private void OnDestroy()
    {
        _runtime?.Stop();
        _runtime = null;
    }

    private sealed class BepInExModLogger : IModLogger
    {
        private readonly ManualLogSource _logger;

        public BepInExModLogger(ManualLogSource logger)
        {
            _logger = logger;
        }

        public void LogInfo(string message) => _logger.LogInfo(message);

        public void LogDebug(string message) => _logger.LogDebug(message);
    }

    private sealed class BepInExJusticeSettings : IJusticeSettings
    {
        private readonly ConfigEntry<bool> _enabled;
        private readonly ConfigEntry<bool> _enableLogging;
        private readonly ConfigEntry<int> _rescanInterval;
        private readonly ConfigEntry<bool> _hideNameplates;
        private readonly ConfigEntry<bool> _hideDamageNumbers;
        private readonly ConfigEntry<bool> _hideTargetRings;
        private readonly ConfigEntry<bool> _hideXPOrbs;
        private readonly ConfigEntry<bool> _hideCastBars;
        private readonly ConfigEntry<bool> _hideOtherWorldText;

        public BepInExJusticeSettings(ConfigFile config)
        {
            _enabled = config.Bind(
                "General",
                "Enabled",
                true,
                "Master switch. When false, F7 behaves as vanilla."
            );
            _enableLogging = config.Bind(
                "General",
                "EnableLogging",
                true,
                "Enable debug logging. Set to false to silence all mod log output."
            );
            _rescanInterval = config.Bind(
                "General",
                "RescanInterval",
                30,
                "Frames between re-scans while UI is hidden (0 = disable re-scan)."
            );
            _hideNameplates = config.Bind(
                "Elements",
                "HideNameplates",
                true,
                "Hide NPC, SimPlayer, and player nameplates."
            );
            _hideDamageNumbers = config.Bind(
                "Elements",
                "HideDamageNumbers",
                true,
                "Hide floating damage and heal numbers."
            );
            _hideTargetRings = config.Bind(
                "Elements",
                "HideTargetRings",
                true,
                "Hide the selection ring under targeted characters."
            );
            _hideXPOrbs = config.Bind("Elements", "HideXPOrbs", true, "Hide XP orb particles.");
            _hideCastBars = config.Bind(
                "Elements",
                "HideCastBars",
                true,
                "Hide NPC and SimPlayer cast bars above nameplates."
            );
            _hideOtherWorldText = config.Bind(
                "Elements",
                "HideOtherWorldText",
                true,
                "Hide remaining world-space text (loot prompts, etc.)."
            );
        }

        public bool Enabled => _enabled.Value;
        public bool EnableLogging => _enableLogging.Value;
        public int RescanInterval => _rescanInterval.Value;
        public bool HideNameplates => _hideNameplates.Value;
        public bool HideDamageNumbers => _hideDamageNumbers.Value;
        public bool HideTargetRings => _hideTargetRings.Value;
        public bool HideXPOrbs => _hideXPOrbs.Value;
        public bool HideCastBars => _hideCastBars.Value;
        public bool HideOtherWorldText => _hideOtherWorldText.Value;
    }
}

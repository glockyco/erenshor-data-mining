using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using InteractiveMapCompanion.Config;
using UnityEngine;
using ConfigLogLevel = InteractiveMapCompanion.Config.LogLevel;

namespace InteractiveMapCompanion;

[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    private InteractiveMapRuntime? _runtime;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        var config = new BepModConfig(Config);
        var log = new BepModLogger(Logger);
        _runtime = new InteractiveMapRuntime(gameObject, config, log);
        _runtime.Start();
    }

    private void Update()
    {
        _runtime?.Tick(Time.deltaTime);
    }

    private void OnApplicationQuit()
    {
        _runtime?.NotifyApplicationQuitting();
    }

    private void OnDestroy()
    {
        _runtime?.Stop();
    }

    private sealed class BepModLogger : IModLogger
    {
        private readonly ManualLogSource _logger;

        internal BepModLogger(ManualLogSource logger)
        {
            _logger = logger;
        }

        public void LogDebug(string message) => _logger.LogDebug(message);

        public void LogInfo(string message) => _logger.LogInfo(message);

        public void LogWarning(string message) => _logger.LogWarning(message);

        public void LogError(string message) => _logger.LogError(message);
    }

    private sealed class BepModConfig : ModConfigBase
    {
        private readonly ConfigEntry<int> _port;
        private readonly ConfigEntry<int> _updateInterval;
        private readonly ConfigEntry<bool> _enableSpawnTracking;
        private readonly ConfigEntry<bool> _enableThirdPartyMarkers;
        private readonly ConfigEntry<bool> _enableBidirectional;
        private readonly ConfigEntry<ConfigLogLevel> _webSocketLogLevel;
        private readonly ConfigEntry<ConfigLogLevel> _modLogLevel;
        private readonly ConfigEntry<bool> _enableOverlay;
        private readonly ConfigEntry<KeyCode> _toggleKey;
        private readonly ConfigEntry<float> _anchorX;
        private readonly ConfigEntry<float> _anchorY;
        private readonly ConfigEntry<int> _overlayWidth;
        private readonly ConfigEntry<int> _overlayHeight;
        private readonly ConfigEntry<bool> _resetToDefaults;

        internal BepModConfig(ConfigFile config)
        {
            _port = config.Bind(
                "Server",
                "Port",
                18585,
                "WebSocket server port. Clients connect to ws://localhost:{port}"
            );
            _updateInterval = config.Bind(
                "Server",
                "UpdateInterval",
                100,
                "Interval in milliseconds between state broadcasts to clients"
            );
            _enableSpawnTracking = config.Bind(
                "Features",
                "EnableSpawnTracking",
                true,
                "Track enemy deaths and broadcast respawn timers"
            );
            _enableThirdPartyMarkers = config.Bind(
                "Features",
                "EnableThirdPartyMarkers",
                true,
                "Allow other mods to register custom markers via the API"
            );
            _enableBidirectional = config.Bind(
                "Features",
                "EnableBidirectional",
                true,
                "Accept messages from clients (waypoints, pings, commands)"
            );
            _webSocketLogLevel = config.Bind(
                "Logging",
                "WebSocketLogLevel",
                ConfigLogLevel.Warning,
                "Log level for WebSocket library. Debug shows all messages (verbose), Warning shows only issues (recommended)."
            );
            _modLogLevel = config.Bind(
                "Logging",
                "ModLogLevel",
                ConfigLogLevel.Info,
                "Log level for the mod itself. Debug shows detailed diagnostics, Info shows important events (recommended)."
            );
            _enableOverlay = config.Bind(
                "Overlay",
                "EnableOverlay",
                true,
                "Show the interactive map as an in-game overlay panel (requires Steam)"
            );
            _toggleKey = config.Bind(
                "Overlay",
                "ToggleKey",
                KeyCode.M,
                "Key to show/hide the in-game map overlay"
            );
            _anchorX = config.Bind(
                "Overlay",
                "AnchorX",
                -1f,
                "Normalized horizontal anchor for the overlay panel (0 = left edge, 1 = right edge). -1 = auto (centred, computed on first run)"
            );
            _anchorY = config.Bind(
                "Overlay",
                "AnchorY",
                -1f,
                "Normalized vertical anchor for the overlay panel (0 = bottom, 1 = top). -1 = auto (centred, computed on first run)"
            );
            _overlayWidth = config.Bind(
                "Overlay",
                "Width",
                0,
                "Width of the in-game map overlay in pixels. 0 = auto (80% of screen width, computed on first run)"
            );
            _overlayHeight = config.Bind(
                "Overlay",
                "Height",
                0,
                "Height of the in-game map overlay in pixels. 0 = auto (80% of screen height, computed on first run)"
            );
            _resetToDefaults = config.Bind(
                "Overlay",
                "ResetToDefaults",
                false,
                "Set to true to reset size and position to auto-computed defaults on next game launch. Resets itself to false automatically."
            );
        }

        public override int Port => _port.Value;
        public override int UpdateInterval => _updateInterval.Value;
        public override bool EnableSpawnTracking => _enableSpawnTracking.Value;
        public override bool EnableThirdPartyMarkers => _enableThirdPartyMarkers.Value;
        public override bool EnableBidirectional => _enableBidirectional.Value;
        public override ConfigLogLevel WebSocketLogLevel => _webSocketLogLevel.Value;
        public override ConfigLogLevel ModLogLevel => _modLogLevel.Value;
        public override bool EnableOverlay => _enableOverlay.Value;
        public override KeyCode ToggleKey => _toggleKey.Value;
        public override float AnchorX
        {
            get => _anchorX.Value;
            set => _anchorX.Value = value;
        }
        public override float AnchorY
        {
            get => _anchorY.Value;
            set => _anchorY.Value = value;
        }
        public override int OverlayWidth
        {
            get => _overlayWidth.Value;
            set => _overlayWidth.Value = value;
        }
        public override int OverlayHeight
        {
            get => _overlayHeight.Value;
            set => _overlayHeight.Value = value;
        }
        public override bool ResetToDefaults
        {
            get => _resetToDefaults.Value;
            set => _resetToDefaults.Value = value;
        }
    }
}

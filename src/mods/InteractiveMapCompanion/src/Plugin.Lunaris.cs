using System.Reflection;
using ErenshorMods.Input;
using InteractiveMapCompanion.Config;
using Lunaris;
using Lunaris.Config;
using UnityEngine;

namespace InteractiveMapCompanion;

[LunarisPlugin(
    "Interactive Map Companion",
    PluginInfo.Version,
    "WoW_Much",
    "Live companion for the Erenshor interactive world map."
)]
// Lunaris compares this with the APIs the DLL calls and flags a plugin whose declaration
// leaves one out. It counts any System.IO call, such as an IOException in the WebRTC
// transport, as file access, and any System.Reflection.Emit call, such as the minimap
// transpiler's opcode comparisons, as unsafe code.
[LunarisPermission(
    LunarisPermission.Network
        | LunarisPermission.Harmony
        | LunarisPermission.Reflection
        | LunarisPermission.FileAccess
        | LunarisPermission.Unsafe
        | LunarisPermission.LunarisPlugin
)]
public sealed class Plugin : LunarisPlugin
{
    private InteractiveMapRuntime? _runtime;
    private MapSettings? _settings;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        _settings = Config.Register<MapSettings>().Get();
        var config = new LunarisModConfig(_settings, Config);
        var log = new LunarisModLogger(Logging);
        _runtime = new InteractiveMapRuntime(gameObject, config, log);
        _runtime.Start();
    }

    private void Update()
    {
        bool togglePressed =
            _settings != null
            && KeyboardShortcuts.WasPressed(_settings.ToggleKey, UnityKeyboardInput.Instance);
        _runtime?.Tick(Time.deltaTime, togglePressed);
    }

    private void OnApplicationQuit()
    {
        _runtime?.NotifyApplicationQuitting();
    }

    private void OnDestroy()
    {
        _runtime?.Stop();
        _runtime = null;
        _settings = null;
    }

    private sealed class LunarisModLogger : IModLogger
    {
        private readonly ILog _logger;

        internal LunarisModLogger(ILog logger)
        {
            _logger = logger;
        }

        public void LogDebug(string message) => _logger.LogDebug(message);

        public void LogInfo(string message) => _logger.LogInfo(message);

        public void LogWarning(string message) => _logger.LogWarning(message);

        public void LogError(string message) => _logger.LogError(message);
    }

    /// <summary>
    /// The overlay settings come from the registered <see cref="MapSettings"/>. The sharing
    /// values change at runtime, so they are read and written through the config directly,
    /// as AdventureGuide's Lunaris backend does, and the generated identity stays out of
    /// the options screen.
    /// </summary>
    private sealed class LunarisModConfig : ModConfigBase
    {
        private const string SharingEnabledKey = "Sharing.Enabled";
        private const string SharingIdentityKey = "Sharing.Identity";

        private readonly MapSettings _settings;
        private readonly IConfig _config;
        private bool _sharingEnabled;
        private string _sharingIdentity;

        internal LunarisModConfig(MapSettings settings, IConfig config)
        {
            _settings = settings;
            _config = config;
            _sharingEnabled = config.Read(SharingEnabledKey, false);
            _sharingIdentity = config.Read(SharingIdentityKey, "");
            config.SetSection(SharingEnabledKey, "Sharing");
            config.SetDesc(
                SharingEnabledKey,
                "Let phones and other PCs on the same network show the live map, through the port after Server.Port. The map's Live panel turns this on and off."
            );
            config.SetSection(SharingIdentityKey, "Sharing");
            config.SetDesc(
                SharingIdentityKey,
                "Pairing credentials the mod generates for other devices. Clear it to unpair every device."
            );
            config
                .GetType()
                .GetMethod("HideKey", BindingFlags.Instance | BindingFlags.NonPublic)
                ?.Invoke(config, new object[] { SharingIdentityKey });
        }

        public override int Port => _settings.Port;
        public override int UpdateInterval => _settings.UpdateInterval;
        public override LogLevel WebSocketLogLevel => _settings.WebSocketLogLevel;
        public override LogLevel ModLogLevel => _settings.ModLogLevel;
        public override bool EnableOverlay => _settings.EnableOverlay;
        public override KeyCode ToggleKey => _settings.ToggleKey;
        public override float AnchorX
        {
            get => _settings.AnchorX;
            set => _settings.AnchorX = value;
        }
        public override float AnchorY
        {
            get => _settings.AnchorY;
            set => _settings.AnchorY = value;
        }
        public override int OverlayWidth
        {
            get => _settings.OverlayWidth;
            set => _settings.OverlayWidth = value;
        }
        public override int OverlayHeight
        {
            get => _settings.OverlayHeight;
            set => _settings.OverlayHeight = value;
        }
        public override bool ResetToDefaults
        {
            get => _settings.ResetToDefaults;
            set => _settings.ResetToDefaults = value;
        }
        public override bool SharingEnabled
        {
            get => _sharingEnabled;
            set
            {
                if (_sharingEnabled == value)
                    return;
                _sharingEnabled = value;
                _config.Write(SharingEnabledKey, value);
            }
        }
        public override string SharingIdentity
        {
            get => _sharingIdentity;
            set
            {
                if (_sharingIdentity == value)
                    return;
                _sharingIdentity = value;
                _config.Write(SharingIdentityKey, value);
            }
        }
    }

    public sealed class MapSettings
    {
        [Config(
            "Port",
            "Server",
            "WebSocket server port. Clients connect to ws://localhost:{port}"
        )]
        public int Port { get; set; } = 18585;

        [Config(
            "UpdateInterval",
            "Server",
            "Interval in milliseconds between state broadcasts to clients"
        )]
        public int UpdateInterval { get; set; } = 100;

        [Config(
            "WebSocketLogLevel",
            "Logging",
            "Log level for WebSocket library. Debug shows all messages (verbose), Warning shows only issues (recommended)."
        )]
        public LogLevel WebSocketLogLevel { get; set; } = LogLevel.Warning;

        [Config(
            "ModLogLevel",
            "Logging",
            "Log level for the mod itself. Debug shows detailed diagnostics, Info shows important events (recommended)."
        )]
        public LogLevel ModLogLevel { get; set; } = LogLevel.Info;

        [Config(
            "EnableOverlay",
            "Overlay",
            "Show the interactive map as an in-game overlay panel (requires Steam)"
        )]
        public bool EnableOverlay { get; set; } = true;

        [Config("ToggleKey", "Overlay", "Key to show/hide the in-game map overlay")]
        public KeyCode ToggleKey { get; set; } = KeyCode.M;

        [Config(
            "AnchorX",
            "Overlay",
            "Normalized horizontal anchor for the overlay panel (0 = left edge, 1 = right edge). -1 = auto (centred, computed on first run)"
        )]
        public float AnchorX { get; set; } = -1f;

        [Config(
            "AnchorY",
            "Overlay",
            "Normalized vertical anchor for the overlay panel (0 = bottom, 1 = top). -1 = auto (centred, computed on first run)"
        )]
        public float AnchorY { get; set; } = -1f;

        [Config(
            "Width",
            "Overlay",
            "Width of the in-game map overlay in pixels. 0 = auto (80% of screen width, computed on first run)"
        )]
        public int OverlayWidth { get; set; } = 0;

        [Config(
            "Height",
            "Overlay",
            "Height of the in-game map overlay in pixels. 0 = auto (80% of screen height, computed on first run)"
        )]
        public int OverlayHeight { get; set; } = 0;

        [Config(
            "ResetToDefaults",
            "Overlay",
            "Set to true to reset size and position to auto-computed defaults on next game launch. Resets itself to false automatically."
        )]
        public bool ResetToDefaults { get; set; } = false;
    }
}

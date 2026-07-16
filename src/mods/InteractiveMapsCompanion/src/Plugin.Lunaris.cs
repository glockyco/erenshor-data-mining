using Lunaris;
using Lunaris.Config;
using UnityEngine;

namespace InteractiveMapsCompanion;

/// <summary>
/// Lunaris adapter for the legacy Interactive Maps Companion runtime.
/// </summary>
[LunarisPlugin(
    "Interactive Maps Companion",
    PluginInfo.Version,
    "WoW_Much",
    "Legacy player-position companion for the interactive maps."
)]
[LunarisPermission(LunarisPermission.Network | LunarisPermission.LunarisPlugin)]
public sealed class Plugin : LunarisPlugin
{
    private InteractiveMapsRuntime? _runtime;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        var settings = Config.Register<InteractiveMapsSettings>().Get();
        var logger = new LunarisModLogger(Logging);
        _runtime = new InteractiveMapsRuntime(settings, logger);
        logger.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private void OnEnable()
    {
        _runtime?.Enable();
    }

    private void Start()
    {
        _runtime?.Start();
    }

    private void Update()
    {
        _runtime?.Tick();
    }

    private void OnDisable()
    {
        _runtime?.Disable();
    }

    private void OnDestroy()
    {
        _runtime?.Stop();
    }

    private sealed class LunarisModLogger : IModLogger
    {
        private readonly ILog _logger;

        public LunarisModLogger(ILog logger)
        {
            _logger = logger;
        }

        public void LogInfo(string message)
        {
            _logger.LogInfo(message);
        }

        public void LogDebug(string message)
        {
            _logger.LogDebug(message);
        }

        public void LogError(string message)
        {
            _logger.LogError(message);
        }
    }
}

/// <summary>
/// Lunaris-registered settings matching the legacy BepInEx defaults.
/// </summary>
public sealed class InteractiveMapsSettings : IModSettings
{
    [Config("Enable Logging", "Debug", "Enable/disable all logging output from this plugin.")]
    public bool EnableLogging { get; set; } = false;

    [Config("Send Interval", "Network", "How often to send position updates (in seconds).")]
    public float SendInterval { get; set; } = 0.1f;
}

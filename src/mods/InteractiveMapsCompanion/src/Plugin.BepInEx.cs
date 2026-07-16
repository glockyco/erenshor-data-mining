using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using UnityEngine;

namespace InteractiveMapsCompanion;

/// <summary>
/// BepInEx adapter for the legacy Interactive Maps Companion runtime.
/// </summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    private InteractiveMapsRuntime? _runtime;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        var enableLogging = Config.Bind(
            "Debug",
            "EnableLogging",
            false,
            "Enable/disable all logging output from this plugin."
        );
        var sendInterval = Config.Bind(
            "Network",
            "SendInterval",
            0.1f,
            "How often to send position updates (in seconds)."
        );

        var settings = new BepModSettings(enableLogging, sendInterval);
        var logger = new BepModLogger(Logger);
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

    private sealed class BepModSettings : IModSettings
    {
        private readonly ConfigEntry<bool> _enableLogging;
        private readonly ConfigEntry<float> _sendInterval;

        public BepModSettings(ConfigEntry<bool> enableLogging, ConfigEntry<float> sendInterval)
        {
            _enableLogging = enableLogging;
            _sendInterval = sendInterval;
        }

        public bool EnableLogging => _enableLogging.Value;

        public float SendInterval => _sendInterval.Value;
    }

    private sealed class BepModLogger : IModLogger
    {
        private readonly ManualLogSource _logger;

        public BepModLogger(ManualLogSource logger)
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

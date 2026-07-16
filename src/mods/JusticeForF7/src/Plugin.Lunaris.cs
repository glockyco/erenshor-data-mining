using Lunaris;
using UnityEngine;

namespace JusticeForF7;

/// <summary>Native Lunaris entry point for Justice for F7.</summary>
[LunarisPlugin(
    PluginInfo.Name,
    PluginInfo.Version,
    "WoW_Much",
    "Extend the F7 Hide UI key to hide world-space UI too."
)]
[LunarisPermission(LunarisPermission.Harmony | LunarisPermission.LunarisPlugin)]
public sealed class Plugin : LunarisPlugin
{
    private JusticeRuntime? _runtime;

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        var settings = Config.Register<JusticeSettings>().Get();
        _runtime = new JusticeRuntime(new LunarisModLogger(Logging), settings);
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

    private sealed class LunarisModLogger : IModLogger
    {
        private readonly ILog _logger;

        public LunarisModLogger(ILog logger)
        {
            _logger = logger;
        }

        public void LogInfo(string message) => _logger.LogInfo(message);

        public void LogDebug(string message) => _logger.LogDebug(message);
    }
}

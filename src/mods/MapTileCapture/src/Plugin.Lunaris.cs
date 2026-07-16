using Lunaris;
using UnityEngine;

namespace MapTileCapture;

[LunarisPlugin(
    PluginInfo.PluginName,
    PluginInfo.Version,
    "WoW_Much",
    "Capture orthographic map tiles from inside Erenshor."
)]
[LunarisPermission(
    LunarisPermission.FileAccess | LunarisPermission.Network | LunarisPermission.LunarisPlugin
)]
public sealed class Plugin : LunarisPlugin
{
    private MapTileCaptureRuntime? _runtime;

    public static float IndoorDirectionalIntensity
    {
        get => MapTileCaptureSettings.IndoorDirectionalIntensity;
        set => MapTileCaptureSettings.IndoorDirectionalIntensity = value;
    }

    public static float IndoorAmbientIntensity
    {
        get => MapTileCaptureSettings.IndoorAmbientIntensity;
        set => MapTileCaptureSettings.IndoorAmbientIntensity = value;
    }

    public static float IndoorDirectionalPitch
    {
        get => MapTileCaptureSettings.IndoorDirectionalPitch;
        set => MapTileCaptureSettings.IndoorDirectionalPitch = value;
    }

    public static float IndoorDirectionalYaw
    {
        get => MapTileCaptureSettings.IndoorDirectionalYaw;
        set => MapTileCaptureSettings.IndoorDirectionalYaw = value;
    }

    public static float BackgroundR
    {
        get => MapTileCaptureSettings.BackgroundR;
        set => MapTileCaptureSettings.BackgroundR = value;
    }

    public static float BackgroundG
    {
        get => MapTileCaptureSettings.BackgroundG;
        set => MapTileCaptureSettings.BackgroundG = value;
    }

    public static float BackgroundB
    {
        get => MapTileCaptureSettings.BackgroundB;
        set => MapTileCaptureSettings.BackgroundB = value;
    }

    public static int DefaultStabilityFrames
    {
        get => MapTileCaptureSettings.DefaultStabilityFrames;
        set => MapTileCaptureSettings.DefaultStabilityFrames = value;
    }

    public static float DefaultSceneLoadTimeoutSecs
    {
        get => MapTileCaptureSettings.DefaultSceneLoadTimeoutSecs;
        set => MapTileCaptureSettings.DefaultSceneLoadTimeoutSecs = value;
    }

    private void Awake()
    {
        gameObject.hideFlags = HideFlags.HideAndDontSave;

        _runtime = new MapTileCaptureRuntime(new LunarisModLogger(Logging), this);
        _runtime.Start();
    }

    private void Update()
    {
        _runtime?.Tick();
    }

    private void OnApplicationQuit()
    {
        _runtime?.NotifyApplicationQuitting();
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

        public void LogDebug(string message) => _logger.LogDebug(message);

        public void LogInfo(string message) => _logger.LogInfo(message);

        public void LogWarning(string message) => _logger.LogWarning(message);

        public void LogError(string message) => _logger.LogError(message);
    }
}

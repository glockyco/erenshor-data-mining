using BepInEx;
using BepInEx.Logging;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Entities;
using InteractiveMapCompanion.Overlay;
using InteractiveMapCompanion.Server;
using InteractiveMapCompanion.State;
using UnityEngine.SceneManagement;

namespace InteractiveMapCompanion;

/// <summary>
/// Main plugin entry point for Interactive Map Companion.
/// Broadcasts real-time game state to the interactive map website via WebSocket.
/// </summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    internal static ManualLogSource Log { get; private set; } = null!;

    private ModConfig? _config;
    private IWebSocketServer? _server;
    private IBroadcastLoop? _broadcastLoop;

    private void Awake()
    {
        Log = Logger;

        _config = new ModConfig(Config);

        var finder = new EntityFinder();
        var classifier = new EntityClassifier();
        var extractor = new EntityExtractor();
        var tracker = new EntityTrackerAdapter(finder, classifier, extractor, _ => true);

        _server = new WebSocketServer(_config, Log);
        _server.Start();

        _broadcastLoop = new BroadcastLoop(
            tracker,
            _server,
            _config,
            msg =>
            {
                if (_config.ModLogLevel.Value == InteractiveMapCompanion.Config.LogLevel.Debug)
                    Log.LogDebug(msg);
            }
        );

        SceneManager.sceneLoaded += OnSceneLoaded;

        var currentScene = SceneManager.GetActiveScene().name;
        _broadcastLoop.OnSceneLoaded(currentScene);

        var overlay = gameObject.AddComponent<MapOverlay>();
        overlay.Config = _config;
        overlay.Log = Log;

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private void Update()
    {
        _broadcastLoop?.Tick(UnityEngine.Time.deltaTime);
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        _broadcastLoop?.OnSceneLoaded(scene.name);
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        _server?.Stop();
    }
}

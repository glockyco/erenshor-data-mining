using HarmonyLib;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Entities;
using InteractiveMapCompanion.Overlay;
using InteractiveMapCompanion.Patches;
using InteractiveMapCompanion.Server;
using InteractiveMapCompanion.State;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace InteractiveMapCompanion;

/// <summary>
/// Loader-neutral composition and lifecycle for Interactive Map Companion.
/// </summary>
public sealed class InteractiveMapRuntime
{
    private readonly GameObject _owner;
    private readonly IModConfig _config;
    private readonly IModLogger _log;

    private Harmony? _harmony;
    private IWebSocketServer? _server;
    private IBroadcastLoop? _broadcastLoop;
    private MapOverlay? _overlay;
    private bool _started;
    private bool _stopped;
    private bool _applicationQuitting;

    public InteractiveMapRuntime(GameObject owner, IModConfig config, IModLogger log)
    {
        _owner = owner;
        _config = config;
        _log = log;
    }

    /// <summary>
    /// Wires and starts all map companion components. Safe to call repeatedly.
    /// </summary>
    public void Start()
    {
        if (_started || _stopped)
            return;

        _started = true;

        try
        {
            var finder = new EntityFinder();
            var classifier = new EntityClassifier();
            var extractor = new EntityExtractor();
            var tracker = new EntityTrackerAdapter(finder, classifier, extractor, _ => true);

            _server = new WebSocketServer(_config, _log);
            _server.Start();

            _broadcastLoop = new BroadcastLoop(
                tracker,
                _server,
                _config,
                message =>
                {
                    if (_config.ModLogLevel == LogLevel.Debug)
                        _log.LogDebug(message);
                }
            );

            SceneManager.sceneLoaded += OnSceneLoaded;
            _broadcastLoop.OnSceneLoaded(SceneManager.GetActiveScene().name);

            _overlay = _owner.AddComponent<MapOverlay>();
            _overlay.Config = _config;
            _overlay.Log = _log;

            _harmony = new Harmony(PluginInfo.GUID);
            _harmony.PatchAll();

            _log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
        }
        catch (Exception ex)
        {
            _log.LogError($"Failed to start {PluginInfo.Name}: {ex}");
            Stop();
        }
    }

    /// <summary>
    /// Advances the overlay shortcut and broadcast loop by one Unity frame.
    /// </summary>
    public void Tick(float deltaTime, bool togglePressed)
    {
        if (!_started || _stopped)
            return;

        _overlay?.HandleShortcut(togglePressed);
        _broadcastLoop?.Tick(deltaTime);
    }

    /// <summary>
    /// Signals the browser before the game's Steam teardown begins.
    /// </summary>
    public void NotifyApplicationQuitting()
    {
        if (_applicationQuitting)
            return;

        _applicationQuitting = true;
        _overlay?.NotifyApplicationQuitting();
    }

    /// <summary>
    /// Stops and cleans up all components. Safe to call repeatedly.
    /// </summary>
    public void Stop()
    {
        if (_stopped)
            return;

        _stopped = true;

        _broadcastLoop?.Stop();
        _server?.Stop();

        _overlay?.Stop();
        if (_overlay != null)
            UnityEngine.Object.Destroy(_overlay);

        SceneManager.sceneLoaded -= OnSceneLoaded;
        _harmony?.UnpatchSelf();
        MapKeyPatches.SuppressMapKey = false;
        CharSelectManagerPatch.ResetPlayerTyping();

        _overlay = null;
        _broadcastLoop = null;
        _server = null;
        _harmony = null;
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        if (_stopped)
            return;

        _broadcastLoop?.OnSceneLoaded(scene.name);

        if (scene.name != "LoadScene")
            CharSelectManagerPatch.ResetPlayerTyping();
    }
}

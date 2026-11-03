using System.Collections.Concurrent;
using HarmonyLib;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Entities;
using InteractiveMapCompanion.Overlay;
using InteractiveMapCompanion.Patches;
using InteractiveMapCompanion.Protocol;
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

    // Sharing changes and messages to local clients run on the main thread. Fleck and
    // WebRTC session threads queue them here for Tick.
    private readonly ConcurrentQueue<Action> _mainThreadWork = new();

    private Harmony? _harmony;
    private IWebSocketServer? _server;
    private LiveSharing? _sharing;
    private volatile string _zone = "";
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

            _zone = SceneManager.GetActiveScene().name;
            _sharing = new LiveSharing(_config, _log, () => BuildHandshake(trusted: false));
            _sharing.Changed += () => _mainThreadWork.Enqueue(SendSharingStatus);
            _sharing.Restore();

            _server = new WebSocketServer(
                _config,
                _log,
                trusted => BuildHandshake(trusted),
                enabled => _mainThreadWork.Enqueue(() => _sharing?.SetEnabled(enabled))
            );
            _server.Start();

            _broadcastLoop = new BroadcastLoop(
                tracker,
                new BroadcastFanOut(_server, _sharing),
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

        while (_mainThreadWork.TryDequeue(out var work))
            work();

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
        _sharing?.Dispose();

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
        _sharing = null;
        _harmony = null;
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        if (_stopped)
            return;

        _zone = scene.name;
        _broadcastLoop?.OnSceneLoaded(scene.name);

        if (scene.name != "LoadScene")
            CharSelectManagerPatch.ResetPlayerTyping();
    }

    /// <summary>
    /// Runs on Fleck and WebRTC threads. Only a trusted map on this PC learns about
    /// sharing, because the status carries the pairing link.
    /// </summary>
    private string BuildHandshake(bool trusted) =>
        MessageSerializer.Serialize(
            HandshakeMessage.Create(
                _zone,
                _config.GetCapabilities(),
                trusted ? _sharing?.Status : null
            )
        );

    private void SendSharingStatus()
    {
        if (_sharing == null || _server == null)
            return;

        _server.BroadcastToTrusted(
            MessageSerializer.Serialize(SharingChangedMessage.Create(_sharing.Status))
        );
    }
}

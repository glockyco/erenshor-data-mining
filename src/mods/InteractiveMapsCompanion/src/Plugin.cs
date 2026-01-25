using BepInEx;
using BepInEx.Configuration;
using Fleck;
using Newtonsoft.Json;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using FleckLogLevel = Fleck.LogLevel;

namespace InteractiveMapsCompanion;

/// <summary>
/// Interactive Maps Companion - Real-time player tracking for zone maps.
/// Legacy mod that broadcasts player position to WebSocket clients.
/// </summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    private ConfigEntry<float> _configSendInterval = null!;
    private ConfigEntry<bool> _configEnableLogging = null!;

    private ConditionalLogger _logger = null!;
    private WebSocketServer? _server;
    private readonly List<IWebSocketConnection> _allSockets = new();

    private float _lastSendTime;
    private Vector3 _lastSentPosition = Vector3.zero;
    private Vector3 _lastSentForward = Vector3.zero;

    private string _currentScene = "";
    private Transform? _playerTransform;

    /// <summary>
    /// Position data sent to WebSocket clients.
    /// </summary>
    [System.Serializable]
    public class PositionData
    {
        [JsonProperty("scene")]
        public string Scene { get; set; } = "";

        [JsonProperty("x")]
        public float X { get; set; }

        [JsonProperty("y")]
        public float Y { get; set; }

        [JsonProperty("z")]
        public float Z { get; set; }

        [JsonProperty("fx")]
        public float ForwardX { get; set; }

        [JsonProperty("fy")]
        public float ForwardY { get; set; }

        [JsonProperty("fz")]
        public float ForwardZ { get; set; }
    }

    private void Awake()
    {
        // Initialize config
        _configEnableLogging = Config.Bind("Debug", "EnableLogging", false, "Enable/disable all logging output from this plugin.");
        _configSendInterval = Config.Bind("Network", "SendInterval", 0.1f, "How often to send position updates (in seconds).");

        // Initialize logger
        _logger = new ConditionalLogger(Logger, _configEnableLogging);

        _logger.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private void OnEnable()
    {
        SceneManager.sceneLoaded += OnSceneLoaded;
    }

    private void OnDisable()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        _logger.LogInfo($"Scene loaded: {scene.name}");
        _currentScene = SceneManager.GetActiveScene().name;
        _playerTransform = FindPlayerTransform();

        if (_playerTransform)
        {
            _logger.LogInfo("Player transform found after scene load.");
        }
        else
        {
            _logger.LogInfo("Player transform not found after scene load.");
        }
    }

    private void Start()
    {
        FleckLog.Level = FleckLogLevel.Warn;

        try
        {
            _server = new WebSocketServer("ws://0.0.0.0:18584");
            _server.Start(socket =>
            {
                socket.OnOpen = () =>
                {
                    _allSockets.Add(socket);
                    _logger.LogInfo($"WebSocket client connected. Total clients: {_allSockets.Count}");

                    if (!_playerTransform) return;

                    var message = CreateMessage(_currentScene, _playerTransform!.position, _playerTransform!.forward);
                    socket.Send(message);
                };

                socket.OnClose = () =>
                {
                    _allSockets.Remove(socket);
                    _logger.LogInfo($"WebSocket client disconnected. Total clients: {_allSockets.Count}");
                };
            });

            _logger.LogInfo("WebSocket server started on ws://0.0.0.0:18584");
        }
        catch (System.Exception ex)
        {
            _logger.LogError($"Failed to start WebSocket server: {ex}");
        }
    }

    private void Update()
    {
        // Find player transform if not already found
        if (!_playerTransform)
        {
            _playerTransform = FindPlayerTransform();
            if (!_playerTransform) return;
        }

        // Check if enough time has passed to send an update
        if (!(Time.time - _lastSendTime >= _configSendInterval.Value)) return;

        var currentPosition = _playerTransform!.position;
        var currentForward = _playerTransform!.forward;

        // Only send if position or rotation changed significantly
        if (ApproximatelyEqual(currentPosition, _lastSentPosition) && ApproximatelyEqual(currentForward, _lastSentForward))
            return;

        _lastSendTime = Time.time;
        _lastSentPosition = currentPosition;
        _lastSentForward = currentForward;

        var message = CreateMessage(_currentScene, currentPosition, currentForward);

        foreach (var socket in _allSockets)
        {
            socket.Send(message);
        }

        _logger.LogDebug($"Sent position update: {message}");
    }

    private void OnDestroy()
    {
        if (_server != null)
        {
            _server.Dispose();
            _logger.LogInfo("WebSocket server stopped.");
        }
    }

    private static string CreateMessage(string scene, Vector3 position, Vector3 forward)
    {
        return JsonConvert.SerializeObject(new PositionData
        {
            Scene = scene,
            X = position.x,
            Y = position.y,
            Z = position.z,
            ForwardX = forward.x,
            ForwardY = forward.y,
            ForwardZ = forward.z
        });
    }

    private static bool ApproximatelyEqual(Vector3 a, Vector3 b, float threshold = 0.001f)
    {
        return Vector3.SqrMagnitude(a - b) < threshold * threshold;
    }

    private static Transform? FindPlayerTransform()
    {
        var playerObj = GameObject.Find("Player");
        return playerObj ? playerObj.transform : null;
    }
}

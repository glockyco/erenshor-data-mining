using BepInEx;
using UnityEngine;
using Fleck;
using System.Collections.Generic;
using BepInEx.Configuration;
using Newtonsoft.Json;
using UnityEngine.SceneManagement;

[BepInPlugin("wow-much.interactive-maps-companion", "Interactive Maps Companion", "0.0.2")]
public class InteractiveMapsCompanion : BaseUnityPlugin
{
    private ConfigEntry<bool> _configEnableLogging;
    private ConfigEntry<float> _configSendInterval;

    private ConditionalLogger _logger;

    private WebSocketServer _server;
    private readonly List<IWebSocketConnection> _allSockets = new List<IWebSocketConnection>();

    private float _lastSendTime;
    private Vector3 _lastSentPosition;
    private Vector3 _lastSentForward;

    private string _currentScene;
    private Transform _playerTransform;

    [System.Serializable]
    public class PositionData
    {
        public string scene;
        public float x, y, z;
        public float fx, fy, fz;
    }

    private void Awake()
    {
        _configEnableLogging = Config.Bind("Debug", "EnableLogging", false, "Enable/disable all logging output from this plugin.");
        _configSendInterval = Config.Bind("Network", "SendInterval", 0.1f, "How often to send position updates (in seconds)."); // 10 times per second
        _logger = new ConditionalLogger(Logger, _configEnableLogging);
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
        FleckLog.Level = LogLevel.Warn;
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

                    socket.Send(CreateMessage(_currentScene, _playerTransform.position, _playerTransform.forward));
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
        if (!_playerTransform)
        {
            _playerTransform = FindPlayerTransform();
            if (!_playerTransform) return;
        }

        if (!(Time.time - _lastSendTime >= _configSendInterval.Value)) return;

        var currentPosition = _playerTransform.position;
        var currentForward = _playerTransform.forward;

        if (ApproximatelyEqual(currentPosition, _lastSentPosition) && ApproximatelyEqual(currentForward, _lastSentForward)) return;

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
        if (_server == null) return;
        _server.Dispose();
        _logger.LogInfo("WebSocket server stopped.");
    }

    private static string CreateMessage(string scene, Vector3 position, Vector3 forward)
    {
        return JsonConvert.SerializeObject(new PositionData
        {
            scene = scene,
            x = position.x,
            y = position.y,
            z = position.z,
            fx = forward.x,
            fy = forward.y,
            fz = forward.z
        });
    }

    private static bool ApproximatelyEqual(Vector3 a, Vector3 b, float threshold = 0.001f)
    {
        return Vector3.SqrMagnitude(a - b) < threshold * threshold;
    }

    private static Transform FindPlayerTransform()
    {
        var playerObj = GameObject.Find("Player");
        return playerObj ? playerObj.transform : null;
    }
}

using Fleck;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.SceneManagement;
using FleckLogLevel = Fleck.LogLevel;

namespace InteractiveMapsCompanion;

/// <summary>
/// Loader-neutral implementation of the legacy player-position companion.
/// </summary>
public sealed class InteractiveMapsRuntime
{
    private const string ServerAddress = "ws://0.0.0.0:18584";
    private const float PositionThreshold = 0.001f;

    private readonly IModSettings _settings;
    private readonly IModLogger _logger;
    private readonly object _lifecycleGate = new();
    private readonly object _socketGate = new();
    private readonly object _stateGate = new();
    private readonly HashSet<IWebSocketConnection> _clients = new();

    private WebSocketServer? _server;
    private bool _starting;
    private bool _started;
    private bool _enabled;
    private bool _stopped;

    private float _lastSendTime;
    private Vector3 _lastSentPosition = Vector3.zero;
    private Vector3 _lastSentForward = Vector3.zero;

    private string _currentScene = "";
    private Transform? _playerTransform;
    private string? _latestMessage;

    public InteractiveMapsRuntime(IModSettings settings, IModLogger logger)
    {
        _settings = settings ?? throw new ArgumentNullException(nameof(settings));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Starts the WebSocket server. A failed start fully tears down the runtime.
    /// </summary>
    public void Start()
    {
        WebSocketServer server;
        lock (_lifecycleGate)
        {
            if (_stopped || _started || _starting)
                return;

            _starting = true;
            server = new WebSocketServer(ServerAddress);
            _server = server;
        }

        FleckLog.Level = FleckLogLevel.Warn;

        try
        {
            server.Start(ConfigureSocket);

            bool disposeAfterStart;
            lock (_lifecycleGate)
            {
                _starting = false;
                disposeAfterStart = _stopped;
                if (!disposeAfterStart)
                    _started = true;
            }

            // Stop() owns disposal when it raced with Fleck's Start call.
            if (disposeAfterStart)
                return;

            LogInfo("WebSocket server started on ws://0.0.0.0:18584");
        }
        catch (Exception ex)
        {
            bool disposeServer;
            lock (_lifecycleGate)
            {
                _starting = false;
                disposeServer = ReferenceEquals(_server, server);
                if (disposeServer)
                    _server = null;
            }

            if (disposeServer)
                DisposeServer(server);

            _logger.LogError($"Failed to start WebSocket server: {ex}");
            Stop();
        }
    }

    /// <summary>
    /// Subscribes to scene changes and synchronizes the currently active scene.
    /// </summary>
    public void Enable()
    {
        lock (_lifecycleGate)
        {
            if (_stopped || _enabled)
                return;

            _enabled = true;
        }

        SceneManager.sceneLoaded += OnSceneLoaded;
        RefreshScene(SceneManager.GetActiveScene().name);
    }

    /// <summary>
    /// Stops scene synchronization without stopping the server.
    /// </summary>
    public void Disable()
    {
        lock (_lifecycleGate)
        {
            _enabled = false;
        }

        // Removing an absent handler is safe and ensures every lifecycle path
        // leaves no scene subscription behind.
        SceneManager.sceneLoaded -= OnSceneLoaded;
    }

    /// <summary>
    /// Sends changed player position and facing data to all connected clients.
    /// Must be called from Unity's main thread.
    /// </summary>
    public void Tick()
    {
        lock (_lifecycleGate)
        {
            if (_stopped || !_started || !_enabled)
                return;
        }

        Transform? player;
        string scene;
        lock (_stateGate)
        {
            player = _playerTransform;
            scene = _currentScene;
        }

        if (player is null || !player)
        {
            player = FindPlayerTransform();
            if (player is null || !player)
                return;

            scene = SceneManager.GetActiveScene().name;
            lock (_stateGate)
            {
                _playerTransform = player;
                _currentScene = scene;
            }
        }

        if (!(Time.time - _lastSendTime >= _settings.SendInterval))
            return;

        var currentPosition = player.position;
        var currentForward = player.forward;
        var message = CreateMessage(scene, currentPosition, currentForward);

        lock (_stateGate)
        {
            _latestMessage = message;
        }

        // Keep the legacy strict threshold and first-update behavior.
        if (
            ApproximatelyEqual(currentPosition, _lastSentPosition)
            && ApproximatelyEqual(currentForward, _lastSentForward)
        )
            return;

        _lastSendTime = Time.time;
        _lastSentPosition = currentPosition;
        _lastSentForward = currentForward;

        Broadcast(message);
        LogDebug($"Sent position update: {message}");
    }

    /// <summary>
    /// Idempotently unsubscribes scenes, closes clients, and disposes Fleck.
    /// </summary>
    public void Stop()
    {
        WebSocketServer? server;
        IWebSocketConnection[] clients;

        lock (_lifecycleGate)
        {
            if (_stopped)
                return;

            _stopped = true;
            _starting = false;
            _started = false;
            _enabled = false;
            server = _server;
            _server = null;
        }

        // Always remove the event, including when Start never completed.
        SceneManager.sceneLoaded -= OnSceneLoaded;

        lock (_socketGate)
        {
            clients = new IWebSocketConnection[_clients.Count];
            _clients.CopyTo(clients);
            _clients.Clear();
        }

        foreach (var client in clients)
            CloseSocket(client);

        if (server != null)
            DisposeServer(server);

        LogInfo("WebSocket server stopped.");
    }

    private void ConfigureSocket(IWebSocketConnection socket)
    {
        socket.OnOpen = () => OnSocketOpened(socket);
        socket.OnClose = () => OnSocketClosed(socket);
    }

    private void OnSocketOpened(IWebSocketConnection socket)
    {
        int clientCount;
        lock (_lifecycleGate)
        {
            if (_stopped)
            {
                CloseSocket(socket);
                return;
            }

            // Keep the lifecycle and client locks ordered the same way as
            // Stop(), so a callback cannot add a client after shutdown clears
            // the collection.
            lock (_socketGate)
            {
                _clients.Add(socket);
                clientCount = _clients.Count;
            }
        }

        LogInfo($"WebSocket client connected. Total clients: {clientCount}");

        // Use the main-thread snapshot: Unity transforms are never read from
        // Fleck's callback thread, while clients still receive an immediate
        // update as soon as a player snapshot exists.
        string? message;
        lock (_stateGate)
        {
            message = _latestMessage;
        }

        if (message != null)
            Send(socket, message);
    }

    private void OnSocketClosed(IWebSocketConnection socket)
    {
        bool removed;
        int clientCount;
        lock (_socketGate)
        {
            removed = _clients.Remove(socket);
            clientCount = _clients.Count;
        }

        if (removed)
            LogInfo($"WebSocket client disconnected. Total clients: {clientCount}");
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        lock (_lifecycleGate)
        {
            if (_stopped || !_enabled)
                return;
        }

        // Match the legacy plugin: report the active scene, not an arbitrary
        // scene argument supplied by Unity's event.
        RefreshScene(SceneManager.GetActiveScene().name);
    }

    private void RefreshScene(string scene)
    {
        var player = FindPlayerTransform();
        string? message = null;
        if (player is not null && player)
            message = CreateMessage(scene, player.position, player.forward);

        lock (_stateGate)
        {
            _currentScene = scene;
            _playerTransform = player;
            _latestMessage = message;
        }

        if (player is not null && player)
            LogInfo("Player transform found after scene load.");
        else
            LogInfo("Player transform not found after scene load.");

        LogInfo($"Scene loaded: {scene}");
    }

    private void Broadcast(string message)
    {
        IWebSocketConnection[] clients;
        lock (_socketGate)
        {
            clients = new IWebSocketConnection[_clients.Count];
            _clients.CopyTo(clients);
        }

        foreach (var client in clients)
            Send(client, message);
    }

    private void Send(IWebSocketConnection socket, string message)
    {
        try
        {
            socket.Send(message);
        }
        catch (Exception ex)
        {
            _logger.LogError($"Failed to send WebSocket update: {ex}");
            lock (_socketGate)
            {
                _clients.Remove(socket);
            }
            CloseSocket(socket);
        }
    }

    private static void CloseSocket(IWebSocketConnection socket)
    {
        try
        {
            socket.Close();
        }
        catch
        {
            // Shutdown is best effort; Fleck may already have closed it.
        }
    }

    private static void DisposeServer(WebSocketServer server)
    {
        try
        {
            server.Dispose();
        }
        catch
        {
            // Fleck may throw when a failed bind is disposed; clients are still
            // closed and the runtime remains stopped.
        }
    }

    private void LogInfo(string message)
    {
        if (_settings.EnableLogging)
            _logger.LogInfo(message);
    }

    private void LogDebug(string message)
    {
        if (_settings.EnableLogging)
            _logger.LogDebug(message);
    }

    private static string CreateMessage(string scene, Vector3 position, Vector3 forward)
    {
        return JsonConvert.SerializeObject(
            new PositionData
            {
                Scene = scene,
                X = position.x,
                Y = position.y,
                Z = position.z,
                ForwardX = forward.x,
                ForwardY = forward.y,
                ForwardZ = forward.z,
            }
        );
    }

    private static bool ApproximatelyEqual(Vector3 a, Vector3 b)
    {
        return Vector3.SqrMagnitude(a - b) < PositionThreshold * PositionThreshold;
    }

    private static Transform? FindPlayerTransform()
    {
        var playerObj = GameObject.Find("Player");
        return playerObj ? playerObj.transform : null;
    }

    /// <summary>
    /// Position data sent by the legacy raw protocol.
    /// </summary>
    [Serializable]
    public sealed class PositionData
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
}

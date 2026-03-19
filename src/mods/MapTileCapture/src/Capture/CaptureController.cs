using System;
using System.Collections;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using BepInEx.Logging;
using MapTileCapture.Server;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MapTileCapture.Capture;

/// <summary>
/// State machine that orchestrates zone captures: scene loading, stabilization,
/// geometry suppression, chunk rendering, and result reporting.
/// </summary>
internal sealed class CaptureController
{
    private enum State { Idle, Loading, Stabilizing, Capturing }

    private static readonly JsonSerializerSettings JsonSettings = new()
    {
        ContractResolver = new Newtonsoft.Json.Serialization.CamelCasePropertyNamesContractResolver(),
        NullValueHandling = NullValueHandling.Include,
        Formatting = Formatting.None,
    };

    private readonly CaptureWebSocketServer _server;
    private readonly MonoBehaviour _coroutineHost;
    private readonly ManualLogSource _logger;

    private State _state = State.Idle;
    private CaptureZoneRequest? _activeRequest;
    private Coroutine? _activeCoroutine;
    private bool _cancelRequested;

    public CaptureController(
        CaptureWebSocketServer server,
        MonoBehaviour coroutineHost,
        ManualLogSource logger)
    {
        _server = server;
        _coroutineHost = coroutineHost;
        _logger = logger;
    }

    /// <summary>
    /// Called every frame from Plugin.Update(). Drains inbound messages and drives the state machine.
    /// </summary>
    public void Tick()
    {
        while (_server.TryDequeue() is { } json)
            HandleMessage(json);
    }

    private void HandleMessage(string json)
    {
        try
        {
            var obj = JObject.Parse(json);
            var messageType = obj["type"]?.ToString();

            if (messageType == null)
            {
                _logger.LogWarning("Received message without 'type' field");
                return;
            }

            switch (messageType)
            {
                case "capture_zone":
                    HandleCaptureZone(json);
                    break;

                case "cancel_capture":
                    HandleCancelCapture();
                    break;

                default:
                    _logger.LogWarning($"Unknown message type: {messageType}");
                    break;
            }
        }
        catch (JsonException ex)
        {
            _logger.LogError($"Failed to parse inbound message: {ex.Message}");
        }
    }

    private void HandleCaptureZone(string json)
    {
        if (_state != State.Idle)
        {
            _logger.LogWarning("Received capture_zone while not idle — ignoring");
            return;
        }

        var request = JsonConvert.DeserializeObject<CaptureZoneRequest>(json, JsonSettings);
        if (request == null)
        {
            SendError("unknown", "unknown", "Failed to deserialize capture_zone request");
            return;
        }

        _activeRequest = request;
        _cancelRequested = false;
        _activeCoroutine = _coroutineHost.StartCoroutine(CaptureCoroutine(request));
    }

    private void HandleCancelCapture()
    {
        if (_state == State.Idle)
            return;

        _logger.LogInfo("Cancel requested");
        _cancelRequested = true;
    }

    private IEnumerator CaptureCoroutine(CaptureZoneRequest request)
    {
        GeometrySuppressor? suppressor = null;
        GameObject? tempCamGo = null;

        try
        {
            // --- Loading ---
            _state = State.Loading;
            _logger.LogInfo($"Loading scene '{request.SceneName}' for zone '{request.Zone}'");

            bool sceneLoaded = false;
            void OnSceneLoaded(Scene scene, LoadSceneMode mode)
            {
                if (scene.name == request.SceneName)
                    sceneLoaded = true;
            }

            SceneManager.sceneLoaded += OnSceneLoaded;
            SceneManager.LoadScene(request.SceneName);

            // Wait for scene to finish loading, with timeout
            float timeout = request.SceneLoadTimeoutSecs > 0 ? request.SceneLoadTimeoutSecs : 30f;
            float elapsed = 0f;
            while (!sceneLoaded)
            {
                if (_cancelRequested)
                {
                    SceneManager.sceneLoaded -= OnSceneLoaded;
                    TransitionToIdle();
                    yield break;
                }

                elapsed += Time.unscaledDeltaTime;
                if (elapsed > timeout)
                {
                    SceneManager.sceneLoaded -= OnSceneLoaded;
                    SendError(request.Zone, request.Variant, $"Scene load timed out after {timeout}s");
                    TransitionToIdle();
                    yield break;
                }

                yield return null;
            }

            SceneManager.sceneLoaded -= OnSceneLoaded;

            // --- Stabilizing ---
            _state = State.Stabilizing;
            int frames = request.StabilityFrames > 0 ? request.StabilityFrames : 10;
            _logger.LogInfo($"Stabilizing for {frames} frames");

            for (int i = 0; i < frames; i++)
            {
                if (_cancelRequested)
                {
                    TransitionToIdle();
                    yield break;
                }
                yield return null;
            }

            // --- Capturing ---
            _state = State.Capturing;

            // Count roof objects before suppression
            int roofObjectCount = ZoneBoundsProbe.CountRoofObjects();

            // Get or create a camera for capture
            var mainCam = Camera.main;
            if (mainCam == null)
            {
                _logger.LogInfo("No main camera in scene \u2014 creating temporary capture camera");
                tempCamGo = new GameObject("MapTileCapture_Camera") { tag = "MainCamera" };
                mainCam = tempCamGo.AddComponent<Camera>();
                mainCam.cullingMask = ~0; // render everything
                mainCam.enabled = false; // we call Render() manually
            }

            // --- Diagnostic: dump lighting state ---
            _logger.LogInfo($"RenderSettings: ambientMode={RenderSettings.ambientMode}, " +
                $"ambientLight={RenderSettings.ambientLight}, " +
                $"ambientIntensity={RenderSettings.ambientIntensity}, " +
                $"ambientSkyColor={RenderSettings.ambientSkyColor}");
            foreach (var light in UnityEngine.Object.FindObjectsOfType<Light>())
            {
                _logger.LogInfo($"Light: {light.name} type={light.type} enabled={light.enabled} " +
                    $"intensity={light.intensity} color={light.color} " +
                    $"rotation={light.transform.eulerAngles}");
            }

            // Create suppressor — dispose guaranteed via finally
            suppressor = new GeometrySuppressor(
                mainCam,
                request.HideRoofs,
                request.ExclusionRules
            );

            // Read north bearing after suppression (ZoneAnnounce should still exist)
            float northBearing = ZoneBoundsProbe.GetNorthBearing(_logger);

            // Measure zone bounds
            var zoneBounds = ZoneBoundsProbe.MeasureBounds();

            // Render each chunk
            if (request.Chunks != null)
            {
                for (int i = 0; i < request.Chunks.Length; i++)
                {
                    if (_cancelRequested)
                    {
                        TransitionToIdle();
                        yield break; // finally will dispose suppressor
                    }

                    var chunk = request.Chunks[i];
                    _logger.LogInfo($"Rendering chunk {chunk.Index} ({i + 1}/{request.Chunks.Length})");

                    var measured = ChunkRenderer.RenderChunk(mainCam, chunk);

                    SendChunkComplete(request.Zone, request.Variant, chunk.Index, chunk.OutputPath, measured);

                    // Yield a frame between chunks to keep the game responsive
                    yield return null;
                }
            }

            // All chunks done
            SendCaptureZoneComplete(
                request.Zone, request.Variant, roofObjectCount, northBearing, zoneBounds
            );
        }
        finally
        {
            suppressor?.Dispose();
            if (tempCamGo != null)
                UnityEngine.Object.Destroy(tempCamGo);
            TransitionToIdle();
        }
    }

    private void TransitionToIdle()
    {
        _state = State.Idle;
        _activeRequest = null;
        _activeCoroutine = null;
        _cancelRequested = false;
    }

    // --- Outbound messages ---

    private void SendChunkComplete(
        string zone, string variant, int chunkIndex, string path,
        ChunkRenderer.MeasuredBounds measured)
    {
        var msg = new
        {
            type = "chunk_complete",
            zone,
            variant,
            chunkIndex,
            path,
            measuredBounds = new
            {
                minX = measured.MinX,
                minZ = measured.MinZ,
                maxX = measured.MaxX,
                maxZ = measured.MaxZ,
            },
        };
        _server.Send(JsonConvert.SerializeObject(msg, JsonSettings));
    }

    private void SendCaptureZoneComplete(
        string zone, string variant, int roofObjectCount, float northBearing,
        ZoneBoundsProbe.ZoneBounds zoneBounds)
    {
        var msg = new
        {
            type = "capture_zone_complete",
            zone,
            variant,
            roofObjectCount,
            northBearing,
            zoneBounds = new
            {
                minX = zoneBounds.MinX,
                minZ = zoneBounds.MinZ,
                maxX = zoneBounds.MaxX,
                maxZ = zoneBounds.MaxZ,
            },
        };
        _server.Send(JsonConvert.SerializeObject(msg, JsonSettings));
    }

    private void SendError(string zone, string variant, string reason)
    {
        var msg = new { type = "capture_error", zone, variant, reason };
        _server.Send(JsonConvert.SerializeObject(msg, JsonSettings));
        _logger.LogError($"Capture error [{zone}/{variant}]: {reason}");
    }

    // --- Request DTOs ---

    private sealed class CaptureZoneRequest
    {
        [JsonProperty("zone")]
        public string Zone { get; set; } = "";

        [JsonProperty("sceneName")]
        public string SceneName { get; set; } = "";

        [JsonProperty("variant")]
        public string Variant { get; set; } = "";

        [JsonProperty("hideRoofs")]
        public bool HideRoofs { get; set; }

        [JsonProperty("sceneLoadTimeoutSecs")]
        public float SceneLoadTimeoutSecs { get; set; }

        [JsonProperty("stabilityFrames")]
        public int StabilityFrames { get; set; }

        [JsonProperty("exclusionRules")]
        public ExclusionRule[]? ExclusionRules { get; set; }

        [JsonProperty("chunks")]
        public ChunkSpec[]? Chunks { get; set; }
    }
}

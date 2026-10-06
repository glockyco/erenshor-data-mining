using System.Collections;
using MapTileCapture.Protocol;
using MapTileCapture.Server;
using Newtonsoft.Json;
using UnityEngine;

namespace MapTileCapture.Capture;

/// <summary>
/// State machine that orchestrates zone captures: optional auto-login, scene loading,
/// stabilization, geometry suppression, chunk rendering, and result reporting.
/// </summary>
internal sealed class CaptureController : IDisposable
{
    private enum State
    {
        Idle,
        LoggingIn,
        Loading,
        Stabilizing,
        Capturing,
    }

    private static readonly JsonSerializerSettings JsonSettings = new()
    {
        ContractResolver =
            new Newtonsoft.Json.Serialization.CamelCasePropertyNamesContractResolver(),
        NullValueHandling = NullValueHandling.Include,
        Formatting = Formatting.None,
    };

    private readonly CaptureWebSocketServer _server;
    private readonly MonoBehaviour _coroutineHost;
    private readonly IModLogger _logger;

    private State _state = State.Idle;
    private CaptureZoneRequest? _activeRequest;
    private Coroutine? _activeCoroutine;
    private GeometrySuppressor? _suppressor;
    private SceneChangeOperation? _sceneChange;
    private bool _cancelRequested;
    private bool _disposed;

    public CaptureController(
        CaptureWebSocketServer server,
        MonoBehaviour coroutineHost,
        IModLogger logger
    )
    {
        _server = server;
        _coroutineHost = coroutineHost;
        _logger = logger;
    }

    public void Dispose()
    {
        if (_disposed)
            return;

        _disposed = true;
        _cancelRequested = true;

        if (_activeCoroutine != null)
        {
            _coroutineHost.StopCoroutine(_activeCoroutine);
            _activeCoroutine = null;
        }

        _sceneChange?.Dispose();
        _sceneChange = null;
        _suppressor?.Dispose();
        _suppressor = null;
        TransitionToIdle();
    }

    /// <summary>Whether a zone capture runs.</summary>
    public bool IsBusy => _activeCoroutine != null;

    public void HandleCaptureZone(string json)
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

    /// <summary>Answers a capture_zone request that another capture blocks.</summary>
    public void Reject(string json, string reason)
    {
        CaptureZoneRequest? request = null;
        try
        {
            request = JsonConvert.DeserializeObject<CaptureZoneRequest>(json, JsonSettings);
        }
        catch (JsonException)
        {
            // The error below still answers the request.
        }
        SendError(request?.Zone ?? "unknown", request?.Variant ?? "unknown", reason);
    }

    public void Cancel()
    {
        if (_state == State.Idle)
            return;

        _logger.LogInfo("Cancel requested");
        _cancelRequested = true;
    }

    private IEnumerator CaptureCoroutine(CaptureZoneRequest request)
    {
        try
        {
            // --- Auto-login (if player is not yet in-world) ---
            if (!GameSession.InWorld)
            {
                _state = State.LoggingIn;
                _logger.LogInfo("MainCam not found — attempting auto-login.");
                yield return GameSession.EnsureInWorld(_logger);
                if (!GameSession.InWorld)
                {
                    SendError(
                        request.Zone,
                        request.Variant,
                        "Auto-login failed: player not in-world after login attempt. "
                            + "Check BepInEx log for details."
                    );
                    TransitionToIdle();
                    yield break;
                }
            }

            // --- Loading ---
            _state = State.Loading;
            _logger.LogInfo($"Loading scene '{request.SceneName}' for zone '{request.Zone}'");

            float timeout =
                request.SceneLoadTimeoutSecs > 0
                    ? request.SceneLoadTimeoutSecs
                    : MapTileCaptureSettings.DefaultSceneLoadTimeoutSecs;
            var loading = new SceneChangeOperation();
            _sceneChange = loading;
            yield return loading.Run(
                request.SceneName,
                Vector3.zero,
                request.UsingSun,
                0f,
                timeout,
                () => _cancelRequested
            );
            _sceneChange = null;
            if (!loading.Loaded)
            {
                if (loading.Error != null)
                    SendError(request.Zone, request.Variant, loading.Error);
                TransitionToIdle();
                yield break;
            }

            // --- Stabilizing ---
            _state = State.Stabilizing;
            int frames =
                request.StabilityFrames > 0
                    ? request.StabilityFrames
                    : MapTileCaptureSettings.DefaultStabilityFrames;

            for (int i = 0; i < frames; i++)
            {
                if (_cancelRequested)
                {
                    TransitionToIdle();
                    yield break;
                }
                yield return null;
            }

            // --- Atmosphere initialization ---
            // SceneChange calls AtmosphereColors.ForceColors() only for zones with
            // usingSun=true. Indoor/cave zones inherit ambient light and fog from
            // the previous zone. Force it unconditionally so every zone starts from
            // its own atmosphere state regardless of load order.
            var atmos = GameObject.Find("Sun")?.GetComponent("AtmosphereColors");
            if (atmos != null)
            {
                atmos.SendMessage("ForceColors", SendMessageOptions.DontRequireReceiver);
                _logger.LogInfo("Forced AtmosphereColors for zone.");
            }

            // --- Capturing ---
            _state = State.Capturing;

            // Count roof objects before suppression
            int roofObjectCount = ZoneBoundsProbe.CountRoofObjects();

            // MainCam carries the correct culling mask (12287), depth texture mode,
            // and PerfectCulling setup baked for the logged-in player.
            var mainCam = GameObject.Find("MainCam")?.GetComponent<Camera>();
            if (mainCam == null)
            {
                SendError(
                    request.Zone,
                    request.Variant,
                    "MainCam disappeared unexpectedly mid-capture."
                );
                TransitionToIdle();
                yield break;
            }

            // Create suppressor — dispose guaranteed via finally
            _suppressor = new GeometrySuppressor(
                mainCam,
                request.HideRoofs,
                request.UsingSun,
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
                    _logger.LogInfo(
                        $"Rendering chunk {chunk.Index} ({i + 1}/{request.Chunks.Length})"
                    );

                    var measured = ChunkRenderer.RenderChunk(mainCam, chunk);

                    SendChunkComplete(
                        request.Zone,
                        request.Variant,
                        chunk.Index,
                        chunk.OutputPath,
                        measured
                    );

                    // Yield a frame between chunks to keep the game responsive
                    yield return null;
                }
            }

            // All chunks done
            SendCaptureZoneComplete(
                request.Zone,
                request.Variant,
                roofObjectCount,
                northBearing,
                zoneBounds
            );
        }
        finally
        {
            _sceneChange?.Dispose();
            _sceneChange = null;
            _suppressor?.Dispose();
            _suppressor = null;
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
        string zone,
        string variant,
        int chunkIndex,
        string path,
        ChunkRenderer.MeasuredBounds measured
    )
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
        string zone,
        string variant,
        int roofObjectCount,
        float northBearing,
        ZoneBoundsProbe.ZoneBounds zoneBounds
    )
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
        var msg = new
        {
            type = "capture_error",
            zone,
            variant,
            reason,
        };
        _server.Send(JsonConvert.SerializeObject(msg, JsonSettings));
        _logger.LogError($"Capture error [{zone}/{variant}]: {reason}");
    }

    // --- Request DTO ---

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

        /// <summary>
        /// Whether the destination zone uses a sun (outdoor zones: true, indoor/cave: false).
        /// Passed to GameData.SceneChange.ChangeScene so the Sun light and AtmosphereColors
        /// are configured correctly before the scene loads.
        /// </summary>
        [JsonProperty("usingSun")]
        public bool UsingSun { get; set; } = true;

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

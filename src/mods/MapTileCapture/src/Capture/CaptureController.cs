using System.Collections;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using BepInEx.Logging;
using MapTileCapture.Protocol;
using MapTileCapture.Server;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MapTileCapture.Capture;

/// <summary>
/// State machine that orchestrates zone captures: optional auto-login, scene loading,
/// stabilization, geometry suppression, chunk rendering, and result reporting.
/// </summary>
internal sealed class CaptureController
{
    private enum State { Idle, LoggingIn, Loading, Stabilizing, Capturing }

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

        try
        {
            // --- Auto-login (if player is not yet in-world) ---
            // MainCam lives in DontDestroyOnLoad after login. Its absence means
            // we are still on the main menu or character select screen.
            if (GameObject.Find("MainCam") == null)
            {
                _state = State.LoggingIn;
                _logger.LogInfo("MainCam not found — attempting auto-login.");
                yield return EnsureInWorldCoroutine();
                if (GameObject.Find("MainCam") == null)
                {
                    SendError(request.Zone, request.Variant,
                        "Auto-login failed: player not in-world after login attempt. " +
                        "Check BepInEx log for details.");
                    TransitionToIdle();
                    yield break;
                }
            }

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

            // Use GameData.SceneChange.ChangeScene instead of raw SceneManager.LoadScene.
            // ChangeScene sets GameData.usingSun, enables or disables the Sun light,
            // and calls AtmosphereColors.ForceColors() for outdoor zones — all before
            // the new scene loads, so ZoneAnnounce.Start() sees the correct state.
            // This prevents atmosphere contamination between sequential zone captures.
            if (GameData.SceneChange == null)
            {
                SceneManager.sceneLoaded -= OnSceneLoaded;
                SendError(request.Zone, request.Variant,
                    "GameData.SceneChange is null — player must be fully in-world before capturing.");
                TransitionToIdle();
                yield break;
            }

            GameData.SceneChange.ChangeScene(
                request.SceneName, Vector3.zero, request.UsingSun, 0f);

            // Wait for scene to finish loading, with timeout
            float timeout = request.SceneLoadTimeoutSecs > 0 ? request.SceneLoadTimeoutSecs : Plugin.DefaultSceneLoadTimeoutSecs.Value;
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
            int frames = request.StabilityFrames > 0 ? request.StabilityFrames : Plugin.DefaultStabilityFrames.Value;
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
                SendError(request.Zone, request.Variant, "MainCam disappeared unexpectedly mid-capture.");
                TransitionToIdle();
                yield break;
            }

            // Create suppressor — dispose guaranteed via finally
            suppressor = new GeometrySuppressor(
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
            TransitionToIdle();
        }
    }

    /// <summary>
    /// Drives the game through its login flow so captures can proceed without
    /// requiring the player to manually navigate the menus.
    ///
    /// Handles two starting states:
    ///   "Menu"      — clicks the Login button to load the character select screen
    ///   "LoadScene" — selects character slot 0, waits for sim data, enters world
    ///
    /// On completion (success or timeout) the caller checks whether MainCam is
    /// present to determine whether the login succeeded.
    /// </summary>
    private IEnumerator EnsureInWorldCoroutine()
    {
        string scene = SceneManager.GetActiveScene().name;
        _logger.LogInfo($"EnsureInWorld: current scene = '{scene}'");

        // From the main menu: load the character select screen.
        // The Login button calls SceneManager.LoadScene("LoadScene") — replicate
        // that directly rather than simulating a UI click.
        if (scene == "Menu")
        {
            _logger.LogInfo("On Menu — loading character select screen.");
            SceneManager.LoadScene("LoadScene");

            float t = 0f;
            while (SceneManager.GetActiveScene().name != "LoadScene")
            {
                t += Time.unscaledDeltaTime;
                if (t > 30f) { _logger.LogError("Timed out waiting for LoadScene."); yield break; }
                yield return null;
            }

            // Give MonoBehaviours two frames to run their Start() callbacks.
            yield return null;
            yield return null;
        }

        // On the character select screen: pick slot 0 and enter the world.
        if (SceneManager.GetActiveScene().name == "LoadScene")
        {
            var charSelect = UnityEngine.Object.FindObjectOfType<CharSelectManager>();
            if (charSelect == null)
            {
                _logger.LogError("CharSelectManager not found on LoadScene.");
                yield break;
            }

            _logger.LogInfo("Selecting character slot 0.");
            charSelect.SelectSlot(0);

            // CharSelectManager.Update() enables EnterWorld only once
            // LoadedSimplayers == true and the selected slot has a character name.
            _logger.LogInfo("Waiting for character data to load...");
            float t = 0f;
            while (!(GameData.SimMngr?.LoadedSimplayers == true &&
                     GameData.CurrentCharacterSlot?.CharName?.Length > 0))
            {
                t += Time.unscaledDeltaTime;
                if (t > 60f) { _logger.LogError("Timed out waiting for character data."); yield break; }
                yield return null;
            }

            if (GameData.CurrentCharacterSlot!.CharName.Length == 0)
            {
                _logger.LogError("Character slot 0 is empty — cannot enter world.");
                yield break;
            }

            _logger.LogInfo($"Entering world as '{GameData.CurrentCharacterSlot.CharName}'.");
            charSelect.EnterWorld.onClick.Invoke();
        }

        // Wait for the player to land in a game zone. MainCam appears in
        // DontDestroyOnLoad once the world scene has loaded and the player spawned.
        _logger.LogInfo("Waiting for MainCam...");
        float inWorldTimeout = 60f;
        float inWorldElapsed = 0f;
        while (GameObject.Find("MainCam") == null)
        {
            inWorldElapsed += Time.unscaledDeltaTime;
            if (inWorldElapsed > inWorldTimeout)
            {
                _logger.LogError("Timed out waiting for MainCam after login.");
                yield break;
            }
            yield return null;
        }

        _logger.LogInfo("Player is in-world.");
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

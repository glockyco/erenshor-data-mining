using System.Collections;
using MapTileCapture.Protocol;
using MapTileCapture.Server;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MapTileCapture.Capture;

/// <summary>
/// Runs portrait captures one request at a time: logs in when needed, loads
/// the scene of a scene source, finds the subject, renders it through
/// <see cref="PortraitStudio"/>, and reports the result. The first scene load
/// of a batch records where the player stood, and <c>end_portraits</c> takes
/// the player back there, so a batch leaves live play as it found it.
/// </summary>
internal sealed class PortraitController : IDisposable
{
    private sealed class PlayerPlace
    {
        public string Scene { get; set; } = "";
        public Vector3 Position { get; set; }
        public float YRotation { get; set; }
        public bool UsingSun { get; set; }
    }

    private readonly CaptureWebSocketServer _server;
    private readonly MonoBehaviour _coroutineHost;
    private readonly IModLogger _logger;

    private Coroutine? _activeCoroutine;
    private SceneChangeOperation? _sceneChange;
    private PlayerPlace? _start;
    private bool _cancelRequested;
    private bool _disposed;

    public PortraitController(
        CaptureWebSocketServer server,
        MonoBehaviour coroutineHost,
        IModLogger logger
    )
    {
        _server = server;
        _coroutineHost = coroutineHost;
        _logger = logger;
    }

    /// <summary>Whether a capture or the return to the starting place runs.</summary>
    public bool IsBusy => _activeCoroutine != null;

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
    }

    public void HandleCapture(string json)
    {
        CapturePortraitRequest? request;
        try
        {
            request = JsonConvert.DeserializeObject<CapturePortraitRequest>(json);
        }
        catch (JsonException ex)
        {
            SendError("", "", $"Unreadable capture_portrait request: {ex.Message}");
            return;
        }
        if (request == null)
        {
            SendError("", "", "Empty capture_portrait request.");
            return;
        }
        if (IsBusy)
        {
            SendError(request.File, request.StableKey, "Another portrait request is running.");
            return;
        }
        var problem = request.Problem();
        if (problem != null)
        {
            SendError(request.File, request.StableKey, problem);
            return;
        }

        _cancelRequested = false;
        _activeCoroutine = _coroutineHost.StartCoroutine(CaptureCoroutine(request));
    }

    public void HandleEnd()
    {
        if (IsBusy)
        {
            SendError("", "", "Another portrait request is running.");
            return;
        }
        _cancelRequested = false;
        _activeCoroutine = _coroutineHost.StartCoroutine(ReturnCoroutine());
    }

    public void Cancel()
    {
        if (!IsBusy)
            return;

        _logger.LogInfo("Portrait cancel requested");
        _cancelRequested = true;
    }

    /// <summary>Answers a request that another capture blocks.</summary>
    public void Reject(string reason) => SendError("", "", reason);

    private IEnumerator CaptureCoroutine(CapturePortraitRequest request)
    {
        try
        {
            if (!GameSession.InWorld)
            {
                yield return GameSession.EnsureInWorld(_logger);
                if (!GameSession.InWorld)
                {
                    SendError(
                        request.File,
                        request.StableKey,
                        "Auto-login failed: player not in-world after login attempt."
                    );
                    yield break;
                }
            }

            var source = request.Source!;
            if (source.Scene != null && SceneManager.GetActiveScene().name != source.Scene)
            {
                _start ??= CurrentPlace();
                float timeout =
                    request.SceneLoadTimeoutSecs > 0
                        ? request.SceneLoadTimeoutSecs
                        : MapTileCaptureSettings.DefaultSceneLoadTimeoutSecs;
                var loading = new SceneChangeOperation();
                _sceneChange = loading;
                // The portrait lights the subject itself, so the scene's sun does not matter.
                yield return loading.Run(
                    source.Scene,
                    ToVector(source.Landing!),
                    false,
                    0f,
                    timeout,
                    () => _cancelRequested
                );
                _sceneChange = null;
                if (!loading.Loaded)
                {
                    SendError(request.File, request.StableKey, loading.Error ?? "Cancelled");
                    yield break;
                }

                int frames =
                    request.StabilityFrames > 0
                        ? request.StabilityFrames
                        : MapTileCaptureSettings.DefaultStabilityFrames;
                for (int i = 0; i < frames; i++)
                    yield return null;
            }

            if (_cancelRequested)
            {
                SendError(request.File, request.StableKey, "Cancelled");
                yield break;
            }

            Render(request, source);
        }
        finally
        {
            _sceneChange?.Dispose();
            _sceneChange = null;
            _activeCoroutine = null;
        }
    }

    private void Render(CapturePortraitRequest request, PortraitSource source)
    {
        try
        {
            var subject = FindSubject(source);
            var mainCam = GameObject.Find("MainCam")?.GetComponent<Camera>();
            if (mainCam == null)
                throw new PortraitException("MainCam disappeared before the capture.");

            var result = PortraitStudio.Capture(subject, mainCam.cullingMask, request.OutputPath);
            _logger.LogInfo($"Captured {request.File} from {result.ObjectName}");
            var message = new
            {
                type = "portrait_complete",
                file = request.File,
                stableKey = request.StableKey,
                preset = PortraitPreset.Name,
                path = request.OutputPath,
                objectName = result.ObjectName,
                width = result.Width,
                height = result.Height,
                renderers = result.Renderers,
                clipped = result.Clipped,
                meanLuminance = result.MeanLuminance,
            };
            _server.Send(JsonConvert.SerializeObject(message));
        }
        catch (PortraitException ex)
        {
            SendError(request.File, request.StableKey, ex.Message);
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex.ToString());
            SendError(request.File, request.StableKey, $"{ex.GetType().Name}: {ex.Message}");
        }
    }

    /// <summary>The game object that the source names.</summary>
    private static GameObject FindSubject(PortraitSource source)
    {
        if (source.ResourcesPath != null)
        {
            return Resources.Load<GameObject>(source.ResourcesPath)
                ?? throw new PortraitException(
                    $"No prefab at Resources path {source.ResourcesPath}."
                );
        }

        var names = new[] { source.ObjectName, source.NpcName }
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => name!.Trim())
            .ToList();
        var named = Resources
            .FindObjectsOfTypeAll<Character>()
            .Select(character => character.gameObject)
            .Where(candidate => names.Contains(candidate.name.Trim()))
            .ToList();
        if (source.Position != null)
        {
            // A placed character can walk, so the nearest one of its name in
            // the scene is the one that the export placed there.
            var position = ToVector(source.Position);
            return named
                    .Where(candidate => candidate.scene.name == source.Scene)
                    .OrderBy(candidate => (candidate.transform.position - position).sqrMagnitude)
                    .FirstOrDefault()
                ?? throw new PortraitException(
                    $"Scene {source.Scene} has no character named {source.ObjectName}."
                );
        }

        // A prefab outside Resources is in memory while a loaded scene references it.
        var prefabs = named.Where(candidate => !candidate.scene.IsValid()).ToList();
        return prefabs.Count switch
        {
            1 => prefabs[0],
            0 => throw new PortraitException(
                $"Scene {source.Scene} references no prefab named {source.ObjectName}."
            ),
            _ => throw new PortraitException(
                $"{prefabs.Count} loaded prefabs are named {source.ObjectName}."
            ),
        };
    }

    private IEnumerator ReturnCoroutine()
    {
        try
        {
            if (_start == null)
            {
                _server.Send(
                    JsonConvert.SerializeObject(new { type = "portraits_ended", returned = false })
                );
                yield break;
            }

            var start = _start;
            var loading = new SceneChangeOperation();
            _sceneChange = loading;
            yield return loading.Run(
                start.Scene,
                start.Position,
                start.UsingSun,
                start.YRotation,
                MapTileCaptureSettings.DefaultSceneLoadTimeoutSecs,
                () => false
            );
            _sceneChange = null;
            if (!loading.Loaded)
            {
                SendError("", "", $"Returning to {start.Scene} failed: {loading.Error}");
                yield break;
            }

            _start = null;
            _logger.LogInfo($"Returned the player to {start.Scene}");
            _server.Send(
                JsonConvert.SerializeObject(
                    new
                    {
                        type = "portraits_ended",
                        returned = true,
                        scene = start.Scene,
                    }
                )
            );
        }
        finally
        {
            _sceneChange?.Dispose();
            _sceneChange = null;
            _activeCoroutine = null;
        }
    }

    private static PlayerPlace CurrentPlace()
    {
        var player = GameData.PlayerControl.transform;
        return new PlayerPlace
        {
            Scene = SceneManager.GetActiveScene().name,
            Position = player.position,
            YRotation = player.eulerAngles.y,
            UsingSun = GameData.usingSun,
        };
    }

    private static Vector3 ToVector(float[] values) => new(values[0], values[1], values[2]);

    private void SendError(string file, string stableKey, string reason)
    {
        _server.Send(
            JsonConvert.SerializeObject(
                new
                {
                    type = "portrait_error",
                    file,
                    stableKey,
                    reason,
                }
            )
        );
        _logger.LogError($"Portrait error [{file}]: {reason}");
    }
}

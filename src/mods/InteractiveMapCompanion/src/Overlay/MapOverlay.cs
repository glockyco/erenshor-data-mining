using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Patches;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace InteractiveMapCompanion.Overlay;

/// <summary>
/// MonoBehaviour that hosts the in-game map overlay.
/// </summary>
[DefaultExecutionOrder(-100)]
internal sealed class MapOverlay : MonoBehaviour
{
    internal IModLogger? Log { get; set; }
    internal IModConfig? Config { get; set; }

    private Canvas? _canvas;
    private RawImage? _rawImage;
    private BrowserManager? _browser;
    private BrowserRenderer? _renderer;
    private InputForwarder? _input;
    private bool _visible;
    private bool _ready;
    private bool _stopped;
    private bool _applicationQuitting;

    private void Start()
    {
        if (_stopped)
            return;

        if (_applicationQuitting)
        {
            Stop();
            Destroy(this);
            return;
        }

        if (Config == null || Log == null)
        {
            Debug.LogError("[InteractiveMapCompanion] Overlay started without config/logger.");
            Stop();
            Destroy(this);
            return;
        }

        if (!Config.EnableOverlay)
        {
            Log.LogInfo("[Overlay] Overlay disabled via config.");
            Stop();
            Destroy(this);
            return;
        }

        try
        {
            BuildUI();
            StartBrowser();

            if (_browser == null)
                return;

            _ready = true;
        }
        catch (Exception ex)
        {
            Log.LogError($"[Overlay] Failed to initialise: {ex}");
            Stop();
            Destroy(this);
        }
    }

    private void BuildUI()
    {
        var config = Config!;
        var log = Log!;

        if (config.ResetToDefaults)
        {
            config.OverlayWidth = 0;
            config.OverlayHeight = 0;
            config.AnchorX = -1f;
            config.AnchorY = -1f;
            config.ResetToDefaults = false;
            log.LogInfo("[Overlay] Reset size/position to auto-computed defaults.");
        }

        if (config.OverlayWidth <= 0)
        {
            config.OverlayWidth = Mathf.RoundToInt(Screen.width * 0.8f);
            config.OverlayHeight = Mathf.RoundToInt(Screen.height * 0.8f);
            log.LogInfo(
                $"[Overlay] Auto-sized to {config.OverlayWidth}x{config.OverlayHeight} (screen: {Screen.width}x{Screen.height})"
            );
        }

        if (config.AnchorX < 0f)
        {
            config.AnchorX = 0.5f;
            config.AnchorY = 0.5f;
        }

        int width = config.OverlayWidth;
        int height = config.OverlayHeight;
        float anchorX = Mathf.Clamp01(config.AnchorX);
        float anchorY = Mathf.Clamp01(config.AnchorY);

        var canvasGO = new GameObject("MapOverlayCanvas");
        DontDestroyOnLoad(canvasGO);

        _canvas = canvasGO.AddComponent<Canvas>();
        _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        _canvas.sortingOrder = 100;

        canvasGO.AddComponent<CanvasScaler>();
        canvasGO.AddComponent<GraphicRaycaster>();

        var panelGO = new GameObject("MapOverlayPanel");
        panelGO.transform.SetParent(canvasGO.transform, false);

        var panel = panelGO.AddComponent<RectTransform>();
        var anchor = new Vector2(anchorX, anchorY);
        panel.anchorMin = anchor;
        panel.anchorMax = anchor;
        panel.pivot = anchor;
        panel.anchoredPosition = Vector2.zero;
        panel.sizeDelta = new Vector2(width, height);

        var imageGO = new GameObject("MapOverlayImage");
        imageGO.transform.SetParent(panelGO.transform, false);

        _rawImage = imageGO.AddComponent<RawImage>();
        var imageRect = imageGO.GetComponent<RectTransform>();
        imageRect.anchorMin = Vector2.zero;
        imageRect.anchorMax = Vector2.one;
        imageRect.sizeDelta = Vector2.zero;
        imageRect.anchoredPosition = Vector2.zero;

        _input = new InputForwarder(panel, width, height);
        canvasGO.SetActive(false);
    }

    private void StartBrowser()
    {
        if (_rawImage == null)
            return;

        int width = Config!.OverlayWidth;
        int height = Config.OverlayHeight;

        _renderer = new BrowserRenderer(Log!, _rawImage, width, height);
        _browser = new BrowserManager(Log!, _renderer.OnPaint);

        bool ok = _browser.Initialize(width, height, "https://erenshor.compendiums.org/map");
        if (ok)
            return;

        Log!.LogWarning("[Overlay] Browser initialisation failed — overlay will not be shown.");
        _browser.Dispose();
        _browser = null;
    }

    private void Update()
    {
        if (_stopped || !_ready || _browser == null)
            return;

        _renderer?.Update();
        _renderer?.LogDiagnostics(Time.deltaTime);

        bool charNameFocused =
            GameData.InCharSelect
            && EventSystem.current?.currentSelectedGameObject?.name == "InputField (TMP)";

        var config = Config!;
        if (Input.GetKeyDown(config.ToggleKey) && !GameData.PlayerTyping && !charNameFocused)
        {
            SetVisible(!_visible);

            if (config.ToggleKey == InputManager.Map)
                MapKeyPatches.SuppressMapKey = true;
        }

        if (!_visible || !_browser.IsReady)
            return;

        _input?.Tick(_browser.BrowserHandle);
    }

    private void LateUpdate()
    {
        if (_stopped)
            return;

        MapKeyPatches.SuppressMapKey = false;
    }

    private void OnApplicationFocus(bool hasFocus)
    {
        if (_stopped || !_ready || _browser?.IsReady != true)
            return;

        if (!hasFocus || _visible)
            _input?.ResetMouseState(_browser.BrowserHandle);
    }

    internal void NotifyApplicationQuitting()
    {
        _applicationQuitting = true;
        _browser?.NotifyAppIsQuitting();
    }

    private void SetVisible(bool visible)
    {
        if (_stopped)
            return;

        _visible = visible;
        _browser?.SetVisible(visible);

        if (_canvas != null)
            _canvas.gameObject.SetActive(visible);

        if (_browser?.IsReady == true)
            _input?.ResetMouseState(_browser.BrowserHandle);

        Log?.LogDebug($"[Overlay] {(visible ? "Shown" : "Hidden")}.");
    }

    internal void Stop()
    {
        if (_stopped)
            return;

        _stopped = true;
        _ready = false;
        MapKeyPatches.SuppressMapKey = false;

        _browser?.Dispose();
        _browser = null;
        _renderer?.Dispose();
        _renderer = null;
        _input = null;

        if (_canvas != null)
        {
            Destroy(_canvas.gameObject);
            _canvas = null;
        }
    }

    private void OnDestroy()
    {
        Stop();
    }
}

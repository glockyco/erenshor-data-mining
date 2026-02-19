using BepInEx.Logging;
using InteractiveMapCompanion.Config;
using UnityEngine;
using UnityEngine.UI;

namespace InteractiveMapCompanion.Overlay;

/// <summary>
/// MonoBehaviour that hosts the in-game map overlay.
///
/// Usage from Plugin.Awake():
///   var overlay = gameObject.AddComponent&lt;MapOverlay&gt;();
///   overlay.Config = _config;
///   overlay.Log = Log;
///
/// Fields must be set before Unity calls Start(). AddComponent() triggers
/// Awake() synchronously, but Start() runs at the end of the frame, giving
/// callers time to set the public fields first.
///
/// The overlay canvas is a separate GameObject marked DontDestroyOnLoad so
/// it persists across scene transitions. It is hidden during loads and
/// re-shown when the browser is ready.
/// </summary>
internal sealed class MapOverlay : MonoBehaviour
{
    // Set by Plugin.Awake() before Start() runs
    internal ManualLogSource Log { get; set; } = null!;
    internal ModConfig Config { get; set; } = null!;

    private Canvas? _canvas;
    private RawImage? _rawImage;

    private BrowserManager? _browser;
    private BrowserRenderer? _renderer;
    private InputForwarder? _input;

    private bool _visible;
    private bool _ready;

    private void Start()
    {
        if (Config == null || Log == null)
        {
            Plugin.Log.LogError(
                "[Overlay] MapOverlay.Start() called without Config/Log — destroying."
            );
            Destroy(this);
            return;
        }

        if (!Config.EnableOverlay.Value)
        {
            Plugin.Log.LogInfo("[Overlay] Overlay disabled via config.");
            Destroy(this);
            return;
        }

        try
        {
            BuildUI();
            StartBrowser();
            _ready = true;
        }
        catch (Exception ex)
        {
            Log.LogError($"[Overlay] Failed to initialise: {ex}");
        }
    }

    private void BuildUI()
    {
        // Apply reset before reading any size/position values
        if (Config.ResetToDefaults.Value)
        {
            Config.OverlayWidth.Value = 0;
            Config.OverlayHeight.Value = 0;
            Config.AnchorX.Value = -1f;
            Config.AnchorY.Value = -1f;
            Config.ResetToDefaults.Value = false;
            Log.LogInfo("[Overlay] Reset size/position to auto-computed defaults.");
        }

        // Resolve sentinel width/height (0 = auto) from current screen dimensions
        if (Config.OverlayWidth.Value <= 0)
        {
            Config.OverlayWidth.Value = Mathf.RoundToInt(Screen.width * 0.8f);
            Config.OverlayHeight.Value = Mathf.RoundToInt(Screen.height * 0.8f);
            Log.LogInfo(
                $"[Overlay] Auto-sized to {Config.OverlayWidth.Value}x{Config.OverlayHeight.Value} (screen: {Screen.width}x{Screen.height})"
            );
        }

        // Resolve sentinel anchor (-1 = auto) to centred
        if (Config.AnchorX.Value < 0f)
        {
            Config.AnchorX.Value = 0.5f;
            Config.AnchorY.Value = 0.5f;
        }

        int width = Config.OverlayWidth.Value;
        int height = Config.OverlayHeight.Value;
        float anchorX = Mathf.Clamp01(Config.AnchorX.Value);
        float anchorY = Mathf.Clamp01(Config.AnchorY.Value);

        // Dedicated canvas so we control sort order independently of game UI
        var canvasGO = new GameObject("MapOverlayCanvas");
        DontDestroyOnLoad(canvasGO);

        _canvas = canvasGO.AddComponent<Canvas>();
        _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        _canvas.sortingOrder = 100; // above the game's main canvas

        canvasGO.AddComponent<CanvasScaler>();
        canvasGO.AddComponent<GraphicRaycaster>();

        // Panel: anchored and pivoted at the same point so anchoredPosition=(0,0)
        // always places the panel correctly regardless of anchor position.
        var panelGO = new GameObject("MapOverlayPanel");
        panelGO.transform.SetParent(canvasGO.transform, false);

        var panel = panelGO.AddComponent<RectTransform>();
        var anchor = new Vector2(anchorX, anchorY);
        panel.anchorMin = anchor;
        panel.anchorMax = anchor;
        panel.pivot = anchor;
        panel.anchoredPosition = Vector2.zero;
        panel.sizeDelta = new Vector2(width, height);

        // RawImage fills the panel — BrowserRenderer writes the texture here
        var imageGO = new GameObject("MapOverlayImage");
        imageGO.transform.SetParent(panelGO.transform, false);

        _rawImage = imageGO.AddComponent<RawImage>();
        var imageRect = imageGO.GetComponent<RectTransform>();
        imageRect.anchorMin = Vector2.zero;
        imageRect.anchorMax = Vector2.one;
        imageRect.sizeDelta = Vector2.zero;
        imageRect.anchoredPosition = Vector2.zero;

        _input = new InputForwarder(panel, width, height);

        // Start hidden; shown when user presses the toggle key
        canvasGO.SetActive(false);
    }

    private void StartBrowser()
    {
        if (_rawImage == null)
            return;

        int width = Config.OverlayWidth.Value;
        int height = Config.OverlayHeight.Value;

        _renderer = new BrowserRenderer(_rawImage, width, height);
        _browser = new BrowserManager(Log, _renderer.OnPaint);

        bool ok = _browser.Initialize(
            width,
            height,
            "https://erenshor-maps.wowmuch1.workers.dev/map"
        );
        if (!ok)
        {
            Log.LogWarning("[Overlay] Browser initialisation failed — overlay will not be shown.");
            _browser.Dispose();
            _browser = null;
        }
    }

    private void Update()
    {
        if (!_ready || _browser == null)
            return;

        if (Input.GetKeyDown(Config.ToggleKey.Value))
            SetVisible(!_visible);

        if (!_visible || !_browser.IsReady)
            return;

        _input?.Tick(_browser.BrowserHandle);
    }

    private void SetVisible(bool visible)
    {
        _visible = visible;
        _browser?.SetVisible(visible);

        if (_canvas != null)
            _canvas.gameObject.SetActive(visible);

        if (visible)
        {
            // Clear any stale mouse-button state the browser accumulated while
            // hidden. Without this, CEF may think a button is still held down
            // and interpret the first mouse move as a drag/text-selection.
            if (_browser != null && _browser.IsReady)
                _input?.ResetMouseState(_browser.BrowserHandle);
        }
        else
        {
            _input?.ClearFocus();
        }

        Log.LogDebug($"[Overlay] {(visible ? "Shown" : "Hidden")}.");
    }

    private void OnDestroy()
    {
        _browser?.Dispose();
        _renderer?.Dispose();

        if (_canvas != null)
            Destroy(_canvas.gameObject);
    }
}

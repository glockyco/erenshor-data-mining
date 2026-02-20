using BepInEx.Logging;
using Steamworks;

namespace InteractiveMapCompanion.Overlay;

/// <summary>
/// Manages the Steam HTML Surface browser lifecycle: init, create, load, destroy.
///
/// The browser renders offscreen via Chromium (CEF) embedded in the Steam client.
/// Pixel data is delivered via the HTML_NeedsPaint_t callback and consumed by
/// BrowserRenderer. All mandatory dialog callbacks are stubbed to prevent hangs.
///
/// Threading: all Steam API calls must happen on the Unity main thread.
/// SteamAPI.RunCallbacks() is called by the game's SteamManager.Update() — we
/// do not need to pump it ourselves.
/// </summary>
internal sealed class BrowserManager : IDisposable
{
    private readonly ManualLogSource _log;
    private readonly Action<HTML_NeedsPaint_t> _onPaint;

    private HHTMLBrowser _browser;
    private bool _browserReady;
    private bool _initialized;
    private bool _visible = true;
    private bool _disposed;

    // Steamworks callback registrations — must be kept alive (not GC'd)
    private Callback<HTML_NeedsPaint_t>? _paintCallback;
    private Callback<HTML_StartRequest_t>? _startRequestCallback;
    private Callback<HTML_JSAlert_t>? _jsAlertCallback;
    private Callback<HTML_JSConfirm_t>? _jsConfirmCallback;
    private Callback<HTML_FileOpenDialog_t>? _fileOpenDialogCallback;
    private CallResult<HTML_BrowserReady_t>? _browserReadyResult;

    internal BrowserManager(ManualLogSource log, Action<HTML_NeedsPaint_t> onPaint)
    {
        _log = log;
        _onPaint = onPaint;
    }

    /// <summary>
    /// Whether the browser has been created and is ready to render.
    /// </summary>
    internal bool IsReady => _browserReady;

    /// <summary>
    /// The Steam HTML Surface browser handle. Only valid when IsReady is true.
    /// </summary>
    internal HHTMLBrowser BrowserHandle => _browser;

    /// <summary>
    /// Initialise Steam HTML Surface and begin creating the browser.
    /// Call once from the Unity main thread after Steam is confirmed running.
    /// Returns false if initialisation fails (overlay will be disabled).
    /// </summary>
    internal bool Initialize(int width, int height, string url)
    {
        if (_initialized)
            return true;

        if (!SteamHTMLSurface.Init())
        {
            _log.LogWarning("[Overlay] SteamHTMLSurface.Init() failed — map overlay disabled.");
            return false;
        }

        _initialized = true;

        RegisterCallbacks();
        CreateBrowser(width, height, url);

        return true;
    }

    /// <summary>
    /// Pause or resume Chromium rendering. When hidden, SetBackgroundMode(true)
    /// tells the Steam browser to stop generating paint callbacks, saving CPU/GPU.
    /// </summary>
    internal void SetVisible(bool visible)
    {
        _visible = visible;
        if (!_browserReady)
            return;
        SteamHTMLSurface.SetBackgroundMode(_browser, !visible);
    }

    /// <summary>
    /// Resize the browser surface. Safe to call before the browser is ready;
    /// the new size will be applied once it's created.
    /// </summary>
    internal void SetSize(int width, int height)
    {
        if (!_browserReady)
            return;

        SteamHTMLSurface.SetSize(_browser, (uint)width, (uint)height);
    }

    /// <summary>
    /// Navigate the browser to a new URL.
    /// </summary>
    internal void LoadUrl(string url)
    {
        if (!_browserReady)
            return;

        SteamHTMLSurface.LoadURL(_browser, url, null);
    }

    private void RegisterCallbacks()
    {
        // Paint: the browser has new pixel data for us
        _paintCallback = Callback<HTML_NeedsPaint_t>.Create(OnNeedsPaint);

        // StartRequest: MUST respond with AllowStartRequest or browser hangs
        _startRequestCallback = Callback<HTML_StartRequest_t>.Create(OnStartRequest);

        // JS dialogs: MUST respond or browser hangs
        _jsAlertCallback = Callback<HTML_JSAlert_t>.Create(OnJSAlert);
        _jsConfirmCallback = Callback<HTML_JSConfirm_t>.Create(OnJSConfirm);

        // File dialog: MUST respond or browser hangs
        _fileOpenDialogCallback = Callback<HTML_FileOpenDialog_t>.Create(OnFileOpenDialog);
    }

    private void CreateBrowser(int width, int height, string url)
    {
        var call = SteamHTMLSurface.CreateBrowser(null, null);
        _browserReadyResult = CallResult<HTML_BrowserReady_t>.Create(
            (param, ioFailure) => OnBrowserReady(param, ioFailure, width, height, url)
        );
        _browserReadyResult.Set(call);
        _log.LogInfo("[Overlay] Browser creation requested, waiting for ready callback...");
    }

    private void OnBrowserReady(
        HTML_BrowserReady_t param,
        bool ioFailure,
        int width,
        int height,
        string url
    )
    {
        if (ioFailure)
        {
            _log.LogWarning(
                "[Overlay] Browser creation failed (IO failure) — map overlay disabled."
            );
            return;
        }

        // Guard against Dispose() being called in the async window between
        // CreateBrowser and this callback firing. If we're already disposed,
        // release the handle Steam just gave us and bail out.
        if (_disposed)
        {
            SteamHTMLSurface.RemoveBrowser(param.unBrowserHandle);
            return;
        }

        _browser = param.unBrowserHandle;
        _browserReady = true;

        SteamHTMLSurface.SetSize(_browser, (uint)width, (uint)height);
        SteamHTMLSurface.LoadURL(_browser, url, null);
        // Apply the current visibility state. CEF may start throttled by default;
        // passing false explicitly ensures the browser paints at full rate when
        // visible. Use _visible so a SetVisible(false) call that arrived while
        // the browser was being created is respected.
        SteamHTMLSurface.SetBackgroundMode(_browser, !_visible);

        _log.LogInfo($"[Overlay] Browser ready (handle={_browser}), loading {url}");
    }

    private void OnNeedsPaint(HTML_NeedsPaint_t param)
    {
        // Skip paint when hidden or for a different browser handle
        if (!_visible || param.unBrowserHandle != _browser)
            return;

        // Invoke the renderer's paint handler immediately — pBGRA is only valid
        // until the next SteamAPI.RunCallbacks() call.
        _onPaint(param);
    }

    private void OnStartRequest(HTML_StartRequest_t param)
    {
        // HTML_StartRequest_t fires only for full document navigations, not for
        // SvelteKit's client-side pushState/replaceState routing. Allow only
        // requests to the map host; deny everything else (external links, etc.)
        // so the overlay cannot be navigated away from the map.
        //
        // AllowStartRequest MUST be called for every callback regardless of
        // which browser fired it, or that browser will hang indefinitely.
        bool ours = param.unBrowserHandle == _browser;
        bool allowed =
            ours
            && param.pchURL is { } url
            && url.StartsWith(
                "https://erenshor-maps.wowmuch1.workers.dev/",
                StringComparison.Ordinal
            );

        if (ours && !allowed)
            _log.LogDebug($"[Overlay] Blocked navigation to: {param.pchURL}");

        SteamHTMLSurface.AllowStartRequest(param.unBrowserHandle, allowed);
    }

    private void OnJSAlert(HTML_JSAlert_t param)
    {
        // JSDialogResponse MUST be called for every callback or the browser hangs.
        if (param.unBrowserHandle == _browser)
            _log.LogDebug($"[Overlay] JS alert: {param.pchMessage}");

        SteamHTMLSurface.JSDialogResponse(param.unBrowserHandle, true);
    }

    private void OnJSConfirm(HTML_JSConfirm_t param)
    {
        // JSDialogResponse MUST be called for every callback or the browser hangs.
        if (param.unBrowserHandle == _browser)
            _log.LogDebug($"[Overlay] JS confirm: {param.pchMessage}");

        SteamHTMLSurface.JSDialogResponse(param.unBrowserHandle, true);
    }

    private void OnFileOpenDialog(HTML_FileOpenDialog_t param)
    {
        // FileLoadDialogResponse MUST be called for every callback or the browser hangs.
        // The map website has no file upload UI — dismiss immediately with no selection.
        SteamHTMLSurface.FileLoadDialogResponse(param.unBrowserHandle, IntPtr.Zero);
    }

    public void Dispose()
    {
        if (_disposed)
            return;

        _disposed = true;

        // Dispose callbacks first to unregister them from Steamworks.NET's
        // dispatch table before tearing down the Steam API. This eliminates the
        // window where a callback (e.g. HTML_NeedsPaint_t) could fire against an
        // already-torn-down API.
        _paintCallback?.Dispose();
        _startRequestCallback?.Dispose();
        _jsAlertCallback?.Dispose();
        _jsConfirmCallback?.Dispose();
        _fileOpenDialogCallback?.Dispose();
        _browserReadyResult?.Dispose();

        if (_browserReady)
        {
            SteamHTMLSurface.RemoveBrowser(_browser);
            _browserReady = false;
        }

        if (_initialized)
        {
            SteamHTMLSurface.Shutdown();
            _initialized = false;
        }
    }
}

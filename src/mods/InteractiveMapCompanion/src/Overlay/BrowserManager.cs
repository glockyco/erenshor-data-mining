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
    internal const string MapUrl = "https://erenshor.compendiums.org/map";

    // Steam HTML Surface never creates windows for target=_blank links or
    // window.open — those clicks are silently dropped by the embedded browser.
    // Rewrite them inside the page into same-surface navigations, which flow
    // through the regular (allowed) StartRequest path. Idempotent: safe to
    // inject on every finished page load. Uses single quotes only so it can
    // live in a verbatim C# string.
    private const string SameTabNavigationScript =
        @"(function () {
            if (window.__erenshorSameTab) return;
            window.__erenshorSameTab = true;
            window.open = function (url) {
                if (url) window.location.href = url;
                return null;
            };
            document.addEventListener('click', function (e) {
                if (e.defaultPrevented || e.button !== 0) return;
                var link = e.target && e.target.closest ? e.target.closest('a[href]') : null;
                if (!link) return;
                var target = (link.getAttribute('target') || '').toLowerCase();
                if (target !== '_blank' && target !== '_new') return;
                e.preventDefault();
                window.location.href = link.href;
            });
        })();";

    private readonly IModLogger _log;
    private readonly Action<HTML_NeedsPaint_t> _onPaint;

    private HHTMLBrowser _browser;
    private bool _browserReady;
    private bool _initialized;

    // The Unity canvas starts hidden; keep CEF in background mode until the
    // first explicit SetVisible(true) from MapOverlay.
    private bool _visible;
    private bool _disposed;
    private bool _appIsQuitting;
    private bool _canGoBack;
    private bool _canGoForward;
    private string? _pendingNavigationUrl;

    // Steamworks callback registrations — must be kept alive (not GC'd)
    private Callback<HTML_NeedsPaint_t>? _paintCallback;
    private Callback<HTML_StartRequest_t>? _startRequestCallback;
    private Callback<HTML_OpenLinkInNewTab_t>? _openLinkCallback;
    private Callback<HTML_NewWindow_t>? _newWindowCallback;
    private Callback<HTML_FinishedRequest_t>? _finishedRequestCallback;
    private Callback<HTML_JSAlert_t>? _jsAlertCallback;
    private Callback<HTML_JSConfirm_t>? _jsConfirmCallback;
    private Callback<HTML_FileOpenDialog_t>? _fileOpenDialogCallback;
    private Callback<HTML_CanGoBackAndForward_t>? _historyCallback;
    private CallResult<HTML_BrowserReady_t>? _browserReadyResult;

    internal BrowserManager(IModLogger log, Action<HTML_NeedsPaint_t> onPaint)
    {
        _log = log;
        _onPaint = onPaint;
    }

    /// <summary>
    /// Whether the browser has been created and is ready to render.
    /// </summary>
    internal bool IsReady => _browserReady;
    internal bool CanGoBack => _browserReady && _canGoBack;
    internal bool CanGoForward => _browserReady && _canGoForward;

    /// <summary>
    /// Raised whenever readiness or history capability changes.
    /// </summary>
    internal event Action? NavigationStateChanged;

    /// <summary>
    /// Signal that the application is quitting. Steam is about to be shut down
    /// by SteamManager, so RemoveBrowser and SteamHTMLSurface.Shutdown must not
    /// be called when Dispose() runs shortly after.
    /// </summary>
    internal void NotifyAppIsQuitting() => _appIsQuitting = true;

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
        if (_disposed || _appIsQuitting)
            return false;
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
        if (_disposed || _appIsQuitting || !_browserReady)
            return;

        SteamHTMLSurface.SetBackgroundMode(_browser, !visible);
    }

    /// <summary>
    /// Resize the browser surface. Safe to call before the browser is ready;
    /// the new size will be applied once it's created.
    /// </summary>
    internal void SetSize(int width, int height)
    {
        if (_disposed || _appIsQuitting || !_browserReady)
            return;

        SteamHTMLSurface.SetSize(_browser, (uint)width, (uint)height);
    }

    /// <summary>
    /// Navigate the browser to a new URL.
    /// </summary>
    internal void LoadUrl(string url)
    {
        if (_disposed || _appIsQuitting || !_browserReady)
            return;

        SteamHTMLSurface.LoadURL(_browser, url, null);
    }

    internal void GoBack()
    {
        if (_disposed || _appIsQuitting || !CanGoBack)
            return;

        SteamHTMLSurface.GoBack(_browser);
    }

    internal void ProcessPendingNavigation()
    {
        if (_disposed || _appIsQuitting || !_browserReady || _pendingNavigationUrl == null)
            return;

        string url = _pendingNavigationUrl;
        _pendingNavigationUrl = null;

        _log.LogInfo($"[Overlay] Opening external link: {url}");
        SteamHTMLSurface.LoadURL(_browser, url, null);
    }

    internal void GoForward()
    {
        if (_disposed || _appIsQuitting || !CanGoForward)
            return;

        SteamHTMLSurface.GoForward(_browser);
    }

    internal void LoadMap() => LoadUrl(MapUrl);

    private void RegisterCallbacks()
    {
        // Paint: the browser has new pixel data for us
        _paintCallback = Callback<HTML_NeedsPaint_t>.Create(OnNeedsPaint);

        // StartRequest: MUST respond with AllowStartRequest or browser hangs
        _startRequestCallback = Callback<HTML_StartRequest_t>.Create(OnStartRequest);

        // External links commonly request a new tab or window. Steam only
        // reports these — it never opens anything — so reuse the overlay
        // browser and keep the existing Back and Map controls available.
        _openLinkCallback = Callback<HTML_OpenLinkInNewTab_t>.Create(OnOpenLinkInNewTab);
        _newWindowCallback = Callback<HTML_NewWindow_t>.Create(OnNewWindow);

        // Not every Steam client build raises the new-window callbacks.
        // Patch each loaded page so target=_blank and window.open navigate
        // the current surface directly, independent of callback support.
        _finishedRequestCallback = Callback<HTML_FinishedRequest_t>.Create(OnFinishedRequest);

        // JS dialogs: MUST respond or browser hangs
        _jsAlertCallback = Callback<HTML_JSAlert_t>.Create(OnJSAlert);
        _jsConfirmCallback = Callback<HTML_JSConfirm_t>.Create(OnJSConfirm);

        // File dialog: MUST respond or browser hangs
        _fileOpenDialogCallback = Callback<HTML_FileOpenDialog_t>.Create(OnFileOpenDialog);

        // History capability drives the toolbar's disabled states.
        _historyCallback = Callback<HTML_CanGoBackAndForward_t>.Create(OnHistoryChanged);
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
        if (_disposed || _appIsQuitting)
            return;
        if (ioFailure)
        {
            _log.LogWarning(
                "[Overlay] Browser creation failed (IO failure) — map overlay disabled."
            );
            return;
        }

        _browser = param.unBrowserHandle;
        _browserReady = true;
        _canGoBack = false;
        _canGoForward = false;

        SteamHTMLSurface.SetSize(_browser, (uint)width, (uint)height);
        SteamHTMLSurface.LoadURL(_browser, url, null);
        // Apply the current visibility state. The Unity canvas starts hidden,
        // so the browser must remain in background mode until the first
        // explicit SetVisible(true).
        SteamHTMLSurface.SetBackgroundMode(_browser, !_visible);
        NavigationStateChanged?.Invoke();

        _log.LogInfo(
            $"[Overlay] Browser ready (handle={_browser}), surface={width}x{height}, loading {url}"
        );
    }

    private void OnNeedsPaint(HTML_NeedsPaint_t param)
    {
        if (_disposed || _appIsQuitting || !_visible || param.unBrowserHandle != _browser)
            return;

        // pBGRA is only valid until the next SteamAPI.RunCallbacks() call.
        _onPaint(param);
    }

    private void OnStartRequest(HTML_StartRequest_t param)
    {
        if (_disposed || _appIsQuitting)
            return;
        // AllowStartRequest MUST be called for every callback or the browser hangs.
        // The overlay is a normal browser surface, so do not restrict destinations.
        SteamHTMLSurface.AllowStartRequest(param.unBrowserHandle, true);
    }

    private void OnOpenLinkInNewTab(HTML_OpenLinkInNewTab_t param)
    {
        if (_disposed || _appIsQuitting || param.unBrowserHandle != _browser)
            return;

        QueueExternalNavigation(param.pchURL);
    }

    private void OnNewWindow(HTML_NewWindow_t param)
    {
        if (_disposed || _appIsQuitting || param.unBrowserHandle != _browser)
            return;

        QueueExternalNavigation(param.pchURL);
    }

    private void QueueExternalNavigation(string url)
    {
        if (string.IsNullOrWhiteSpace(url))
            return;

        _pendingNavigationUrl = url;
    }

    private void OnFinishedRequest(HTML_FinishedRequest_t param)
    {
        if (_disposed || _appIsQuitting || param.unBrowserHandle != _browser)
            return;

        SteamHTMLSurface.ExecuteJavascript(_browser, SameTabNavigationScript);
    }

    private void OnHistoryChanged(HTML_CanGoBackAndForward_t param)
    {
        if (_disposed || _appIsQuitting || param.unBrowserHandle != _browser)
            return;

        if (_canGoBack == param.bCanGoBack && _canGoForward == param.bCanGoForward)
            return;

        _canGoBack = param.bCanGoBack;
        _canGoForward = param.bCanGoForward;
        NavigationStateChanged?.Invoke();
    }

    private void OnJSAlert(HTML_JSAlert_t param)
    {
        if (_disposed || _appIsQuitting)
            return;
        // JSDialogResponse MUST be called for every callback or the browser hangs.
        if (param.unBrowserHandle == _browser)
            _log.LogDebug($"[Overlay] JS alert: {param.pchMessage}");

        SteamHTMLSurface.JSDialogResponse(param.unBrowserHandle, true);
    }

    private void OnJSConfirm(HTML_JSConfirm_t param)
    {
        if (_disposed || _appIsQuitting)
            return;

        // JSDialogResponse MUST be called for every callback or the browser hangs.
        if (param.unBrowserHandle == _browser)
            _log.LogDebug($"[Overlay] JS confirm: {param.pchMessage}");

        SteamHTMLSurface.JSDialogResponse(param.unBrowserHandle, true);
    }

    private void OnFileOpenDialog(HTML_FileOpenDialog_t param)
    {
        if (_disposed || _appIsQuitting)
            return;
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
        _openLinkCallback?.Dispose();
        _newWindowCallback?.Dispose();
        _finishedRequestCallback?.Dispose();
        _jsAlertCallback?.Dispose();
        _jsConfirmCallback?.Dispose();
        _fileOpenDialogCallback?.Dispose();
        _historyCallback?.Dispose();
        _browserReadyResult?.Dispose();

        // Skip Steam teardown when the application is quitting: SteamManager will
        // call SteamAPI.Shutdown() as part of its own OnDestroy, which tears down
        // the HTML surface along with everything else. Calling RemoveBrowser or
        // SteamHTMLSurface.Shutdown after that point would throw.
        if (!_appIsQuitting)
        {
            if (_browserReady)
                SteamHTMLSurface.RemoveBrowser(_browser);

            if (_initialized)
                SteamHTMLSurface.Shutdown();
        }

        _browserReady = false;
        _initialized = false;
        _canGoBack = false;
        _canGoForward = false;
        _pendingNavigationUrl = null;
        _browser = default;
    }
}

using BepInEx.Logging;
using Steamworks;
using UnityEngine;
using UnityEngine.UI;

namespace InteractiveMapCompanion.Overlay;

/// <summary>
/// Consumes HTML_NeedsPaint_t callbacks from BrowserManager and writes the
/// browser's pixel data into a Texture2D displayed on a Unity RawImage.
///
/// The Steam HTML Surface delivers B8G8R8A8 (BGRA32) pixel data. Unity's
/// TextureFormat.BGRA32 matches this layout exactly — no channel swapping needed.
///
/// Threading: OnPaint is called from the Steam callback, which fires during
/// SteamAPI.RunCallbacks() on the Unity main thread. Texture operations are
/// safe here.
/// </summary>
internal sealed class BrowserRenderer : IDisposable
{
    private Texture2D? _texture;
    private readonly RawImage _rawImage;
    private int _width;
    private int _height;
    private bool _textureDirty;
    private bool _disposed;

    // Diagnostics: track paint stats and emit a summary every 5 seconds.
    private readonly ManualLogSource _log;
    private float _diagTimer;
    private int _diagPaintCount; // OnPaint calls received this interval
    private int _diagUploadCount; // Apply() calls this interval (frames with new data)
    private long _diagDirtyPixels; // sum of dirty-rect pixels across all paints
    private long _diagFullPixels; // sum of full-surface pixels across all paints
    private const float DiagInterval = 5f;

    internal BrowserRenderer(ManualLogSource log, RawImage rawImage, int width, int height)
    {
        _log = log;
        _rawImage = rawImage;
        _width = width;
        _height = height;
        CreateTexture(width, height);
    }

    /// <summary>
    /// Called by BrowserManager when the browser has new pixel data.
    /// pBGRA is only valid for the duration of this call, so we load it
    /// into the texture's CPU-side staging buffer immediately and defer the
    /// GPU upload to Update().
    /// </summary>
    internal void OnPaint(HTML_NeedsPaint_t param)
    {
        int fullWidth = (int)param.unWide;
        int fullHeight = (int)param.unTall;

        // Recreate the texture if the browser surface size has changed
        if (fullWidth != _width || fullHeight != _height)
        {
            _width = fullWidth;
            _height = fullHeight;
            CreateTexture(fullWidth, fullHeight);
        }

        if (_texture == null)
            return;

        // Load pixel data directly from the unmanaged pointer into Unity's
        // internal CPU-side staging buffer in a single copy. This avoids the
        // two-copy pipeline (unmanaged → byte[] → staging buffer) that the
        // byte[] overload of LoadRawTextureData requires.
        //
        // pBGRA is only valid for the duration of this callback, but
        // LoadRawTextureData copies it immediately, so it is safe to use here.
        // The GPU upload (Apply) is deferred to Update() so it doesn't block
        // the Steam callback and back-pressure CEF's paint rate.
        _texture.LoadRawTextureData(param.pBGRA, fullWidth * fullHeight * 4);
        _textureDirty = true;

        // Diagnostics: accumulate dirty-rect vs full-surface coverage.
        _diagPaintCount++;
        _diagDirtyPixels += (long)param.unUpdateWide * param.unUpdateTall;
        _diagFullPixels += (long)fullWidth * fullHeight;
    }

    /// <summary>
    /// Call once per Unity frame. Uploads any pending pixel data to the GPU.
    /// Separating this from OnPaint prevents the GPU upload from blocking the
    /// Steam callback and allows CEF to paint at its full rate.
    /// </summary>
    internal void Update()
    {
        if (!_textureDirty || _texture == null)
            return;

        _textureDirty = false;
        _texture.Apply(updateMipmaps: false, makeNoLongerReadable: false);
        _diagUploadCount++;
    }

    // Called from MapOverlay.Update() — uses Unity time so must be on main thread.
    internal void LogDiagnostics(float deltaTime)
    {
        _diagTimer += deltaTime;
        if (_diagTimer < DiagInterval)
            return;

        float interval = _diagTimer;
        _diagTimer = 0f;

        if (_diagPaintCount == 0)
        {
            _log.LogDebug("[Overlay] Paint diagnostics: no callbacks received.");
            return;
        }

        float paintHz = _diagPaintCount / interval;
        float uploadHz = _diagUploadCount / interval;
        float dirtyPct =
            _diagFullPixels > 0 ? (float)_diagDirtyPixels / _diagFullPixels * 100f : 0f;
        int redundant = _diagPaintCount - _diagUploadCount;

        _log.LogDebug(
            $"[Overlay] Paint: {paintHz:F1} callbacks/s  "
                + $"uploads: {uploadHz:F1}/s  "
                + $"dirty rect avg: {dirtyPct:F1}% of surface  "
                + $"redundant (overwritten before upload): {redundant}"
        );

        _diagPaintCount = 0;
        _diagUploadCount = 0;
        _diagDirtyPixels = 0;
        _diagFullPixels = 0;
    }

    private void CreateTexture(int width, int height)
    {
        if (_texture != null)
            UnityEngine.Object.Destroy(_texture);

        // BGRA32 matches Steam HTML Surface's B8G8R8A8 layout exactly
        _texture = new Texture2D(width, height, TextureFormat.BGRA32, mipChain: false);
        _rawImage.texture = _texture;
        // Steam delivers rows top-to-bottom; Unity Texture2D stores them bottom-to-top.
        // Flipping the UV rect at render time costs nothing and avoids per-frame byte shuffling.
        _rawImage.uvRect = new Rect(0f, 1f, 1f, -1f);
    }

    public void Dispose()
    {
        if (_disposed)
            return;

        _disposed = true;

        if (_texture != null)
        {
            UnityEngine.Object.Destroy(_texture);
            _texture = null;
        }
    }
}

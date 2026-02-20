using System.Runtime.InteropServices;
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
    private byte[] _pixelBuffer = Array.Empty<byte>();
    private bool _textureDirty;
    private bool _disposed;

    internal BrowserRenderer(RawImage rawImage, int width, int height)
    {
        _rawImage = rawImage;
        _width = width;
        _height = height;
        CreateTexture(width, height);
    }

    /// <summary>
    /// Called by BrowserManager when the browser has new pixel data.
    /// pBGRA is only valid for the duration of this call, so we copy it
    /// immediately into _pixelBuffer and defer the GPU upload to Update().
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

        int byteCount = fullWidth * fullHeight * 4;

        // Reuse the buffer to avoid per-frame GC pressure (~6.7 MB at 90% of 1080p).
        // Only reallocate when the surface size changes, which is rare.
        if (_pixelBuffer.Length != byteCount)
            _pixelBuffer = new byte[byteCount];

        // Copy pixel data out of unmanaged memory immediately — pBGRA is only
        // valid until the next SteamAPI.RunCallbacks() call. The GPU upload
        // (LoadRawTextureData + Apply) is deferred to Update() so it doesn't
        // block the Steam callback and back-pressure CEF's paint rate.
        Marshal.Copy(param.pBGRA, _pixelBuffer, 0, byteCount);
        _textureDirty = true;
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
        _texture.LoadRawTextureData(_pixelBuffer);
        // makeNoLongerReadable: true releases Unity's CPU-side copy of the
        // texture data. We never call GetPixels() on _texture — _pixelBuffer
        // is our managed copy — so keeping the CPU copy alive wastes memory.
        _texture.Apply(updateMipmaps: false, makeNoLongerReadable: true);
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

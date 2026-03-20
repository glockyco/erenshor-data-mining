using UnityEngine;

namespace MapTileCapture.Capture;

/// <summary>
/// Specification for a single chunk to render, deserialized from the capture_zone message.
/// </summary>
public sealed class ChunkSpec
{
    public int Index { get; set; }
    public float CenterX { get; set; }
    public float CenterZ { get; set; }
    public float WorldWidth { get; set; }
    public float WorldHeight { get; set; }
    public int PixelWidth { get; set; }
    public int PixelHeight { get; set; }
    public string OutputPath { get; set; } = "";
}

/// <summary>
/// Renders a single orthographic chunk of the world to a PNG file.
/// </summary>
internal static class ChunkRenderer
{
    /// <summary>
    /// Measured bounds of the rendered frustum, returned after capture.
    /// </summary>
    public struct MeasuredBounds
    {
        public float MinX;
        public float MinZ;
        public float MaxX;
        public float MaxZ;
    }

    /// <summary>
    /// Render one chunk to disk as PNG using a temporary orthographic camera.
    /// Returns the measured world-space bounds of the camera frustum.
    /// </summary>
    public static MeasuredBounds RenderChunk(Camera mainCam, ChunkSpec chunk)
    {
        RenderTexture? rt = null;
        Texture2D? tex = null;

        try
        {
            rt = new RenderTexture(chunk.PixelWidth, chunk.PixelHeight, 24);

            // Configure the camera for this chunk
            mainCam.orthographic = true;
            mainCam.orthographicSize = chunk.WorldHeight / 2f;
            mainCam.aspect = chunk.WorldWidth / chunk.WorldHeight;
            mainCam.transform.position = new Vector3(chunk.CenterX, 1000f, chunk.CenterZ);
            mainCam.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            mainCam.nearClipPlane = 0.1f;
            mainCam.farClipPlane = 2000f;
            mainCam.useOcclusionCulling = false;
            mainCam.clearFlags = CameraClearFlags.SolidColor;
            mainCam.backgroundColor = new Color(0f, 0f, 0f, 0f);
            mainCam.depthTextureMode = DepthTextureMode.Depth;
            mainCam.targetTexture = rt;

            mainCam.Render();

            // Read pixels from the render texture
            var previousActive = RenderTexture.active;
            RenderTexture.active = rt;

            tex = new Texture2D(chunk.PixelWidth, chunk.PixelHeight, TextureFormat.RGBA32, false);
            tex.ReadPixels(new Rect(0, 0, chunk.PixelWidth, chunk.PixelHeight), 0, 0);
            tex.Apply();

            RenderTexture.active = previousActive;

            // Write PNG
            var pngBytes = tex.EncodeToPNG();
            var dir = Path.GetDirectoryName(chunk.OutputPath);
            if (!string.IsNullOrEmpty(dir))
                Directory.CreateDirectory(dir);
            File.WriteAllBytes(chunk.OutputPath, pngBytes);

            // Compute measured bounds from the orthographic frustum
            float halfWidth = chunk.WorldWidth / 2f;
            float halfHeight = chunk.WorldHeight / 2f;

            return new MeasuredBounds
            {
                MinX = chunk.CenterX - halfWidth,
                MinZ = chunk.CenterZ - halfHeight,
                MaxX = chunk.CenterX + halfWidth,
                MaxZ = chunk.CenterZ + halfHeight,
            };
        }
        finally
        {
            mainCam.targetTexture = null;

            if (rt != null)
            {
                rt.Release();
                UnityEngine.Object.Destroy(rt);
            }

            if (tex != null)
                UnityEngine.Object.Destroy(tex);
        }
    }
}

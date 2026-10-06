namespace MapTileCapture.Capture;

/// <summary>An inclusive pixel rectangle; rows count from the bottom, as Unity reads pixels.</summary>
public readonly struct PixelBox
{
    public PixelBox(int minX, int minY, int maxX, int maxY)
    {
        MinX = minX;
        MinY = minY;
        MaxX = maxX;
        MaxY = maxY;
    }

    public int MinX { get; }
    public int MinY { get; }
    public int MaxX { get; }
    public int MaxY { get; }
    public int Width => MaxX - MinX + 1;
    public int Height => MaxY - MinY + 1;
}

/// <summary>
/// Pixel operations of a portrait on RGBA32 buffers: four bytes a pixel, rows
/// from the bottom.
/// </summary>
public static class PortraitImage
{
    /// <summary>
    /// The subject with its alpha, from two renders of it over black and over
    /// white. A pixel that both renders show alike is opaque. The more the
    /// background shows through, the more the renders differ, so one minus the
    /// largest channel difference is the pixel's coverage. That also holds for
    /// additive effects, which never write alpha themselves. The colour is the
    /// render over black divided by that coverage.
    /// </summary>
    public static byte[] Matte(byte[] overBlack, byte[] overWhite)
    {
        if (overBlack.Length != overWhite.Length || overBlack.Length % 4 != 0)
            throw new ArgumentException("Both renders must be RGBA32 buffers of one size.");

        var matte = new byte[overBlack.Length];
        for (int i = 0; i < overBlack.Length; i += 4)
        {
            int difference = 0;
            for (int channel = 0; channel < 3; channel++)
                difference = Math.Max(difference, overWhite[i + channel] - overBlack[i + channel]);
            int alpha = Math.Min(255, Math.Max(0, 255 - difference));
            if (alpha == 0)
                continue;
            for (int channel = 0; channel < 3; channel++)
                matte[i + channel] = (byte)Math.Min(255, overBlack[i + channel] * 255 / alpha);
            matte[i + 3] = (byte)alpha;
        }
        return matte;
    }

    /// <summary>The smallest box of the pixels whose alpha exceeds <paramref name="threshold"/>, or null.</summary>
    public static PixelBox? AlphaBox(byte[] rgba, int width, int height, byte threshold)
    {
        int minX = width,
            minY = height,
            maxX = -1,
            maxY = -1;
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                if (rgba[((y * width) + x) * 4 + 3] <= threshold)
                    continue;
                minX = Math.Min(minX, x);
                maxX = Math.Max(maxX, x);
                minY = Math.Min(minY, y);
                maxY = Math.Max(maxY, y);
            }
        }
        return maxX < 0 ? null : new PixelBox(minX, minY, maxX, maxY);
    }

    /// <summary>Whether the box reaches an edge of the image, so the image may cut the subject off.</summary>
    public static bool TouchesBorder(PixelBox box, int width, int height) =>
        box.MinX == 0 || box.MinY == 0 || box.MaxX == width - 1 || box.MaxY == height - 1;

    /// <summary>The box grown by <paramref name="margin"/> pixels on each side, within the image.</summary>
    public static PixelBox Expand(PixelBox box, int margin, int width, int height) =>
        new(
            Math.Max(0, box.MinX - margin),
            Math.Max(0, box.MinY - margin),
            Math.Min(width - 1, box.MaxX + margin),
            Math.Min(height - 1, box.MaxY + margin)
        );

    /// <summary>The pixels of the box, as a buffer of the box's size.</summary>
    public static byte[] Crop(byte[] rgba, int width, PixelBox box)
    {
        var cropped = new byte[box.Width * box.Height * 4];
        for (int row = 0; row < box.Height; row++)
        {
            Buffer.BlockCopy(
                rgba,
                (((box.MinY + row) * width) + box.MinX) * 4,
                cropped,
                row * box.Width * 4,
                box.Width * 4
            );
        }
        return cropped;
    }

    /// <summary>
    /// The mean luminance of the pixels that are at least half opaque, from 0
    /// to 1, or 0 without such pixels.
    /// </summary>
    public static double MeanLuminance(byte[] rgba)
    {
        double sum = 0;
        int count = 0;
        for (int i = 0; i < rgba.Length; i += 4)
        {
            if (rgba[i + 3] < 128)
                continue;
            sum += ((0.2126 * rgba[i]) + (0.7152 * rgba[i + 1]) + (0.0722 * rgba[i + 2])) / 255.0;
            count++;
        }
        return count == 0 ? 0 : sum / count;
    }
}

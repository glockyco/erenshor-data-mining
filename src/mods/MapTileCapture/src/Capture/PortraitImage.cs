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
    /// white. Where the subject covers a pixel with normal blending, both
    /// renders differ by the same amount in every channel: one minus that
    /// difference is its coverage. An additive effect adds light instead, so
    /// it differs least in the channels of its colour. The smallest channel
    /// difference therefore gives coloured glows their brightness as alpha,
    /// where the largest would erase a pure green glow, and it leaves normal
    /// pixels unchanged. The colour is the render over black divided by the
    /// coverage.
    /// </summary>
    public static byte[] Matte(byte[] overBlack, byte[] overWhite)
    {
        if (overBlack.Length != overWhite.Length || overBlack.Length % 4 != 0)
            throw new ArgumentException("Both renders must be RGBA32 buffers of one size.");

        var matte = new byte[overBlack.Length];
        for (int i = 0; i < overBlack.Length; i += 4)
        {
            int difference = 255;
            for (int channel = 0; channel < 3; channel++)
                difference = Math.Min(difference, overWhite[i + channel] - overBlack[i + channel]);
            int alpha = Math.Min(255, Math.Max(0, 255 - difference));
            if (alpha == 0)
                continue;
            for (int channel = 0; channel < 3; channel++)
                matte[i + channel] = (byte)Math.Min(255, overBlack[i + channel] * 255 / alpha);
            matte[i + 3] = (byte)alpha;
        }
        return matte;
    }

    /// <summary>
    /// The matte with the colours of a render through the game's image
    /// effects over black. The effects grade the background too and darken
    /// silhouette edges, so the coverage comes from the plain renders of the
    /// matte, and only the colour from the graded render, divided by that
    /// coverage. The grading keeps black black, so a partly covered pixel of
    /// the graded render holds the graded colour times its coverage.
    /// </summary>
    public static byte[] Graded(byte[] matte, byte[] gradedOverBlack)
    {
        if (matte.Length != gradedOverBlack.Length || matte.Length % 4 != 0)
            throw new ArgumentException(
                "The matte and the graded render must be RGBA32 buffers of one size."
            );

        var graded = new byte[matte.Length];
        for (int i = 0; i < matte.Length; i += 4)
        {
            int alpha = matte[i + 3];
            if (alpha == 0)
                continue;
            for (int channel = 0; channel < 3; channel++)
                graded[i + channel] = (byte)
                    Math.Min(255, gradedOverBlack[i + channel] * 255 / alpha);
            graded[i + 3] = (byte)alpha;
        }
        return graded;
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

    /// <summary>
    /// The box of a subject's pixels: those whose alpha exceeds
    /// <paramref name="threshold"/>, which leaves out faint edges and haze. A
    /// subject that the game draws almost transparent, such as the
    /// Aetherfiend, has no such pixel and is framed by every pixel it draws
    /// instead, so its portrait shows it as faint as the game does. Null when
    /// the subject draws nothing.
    /// </summary>
    public static PixelBox? SubjectBox(byte[] rgba, int width, int height, byte threshold) =>
        AlphaBox(rgba, width, height, threshold) ?? AlphaBox(rgba, width, height, 0);

    /// <summary>Whether the box reaches an edge of the image, so the image may cut the subject off.</summary>
    public static bool TouchesBorder(PixelBox box, int width, int height) =>
        box.MinX == 0 || box.MinY == 0 || box.MaxX == width - 1 || box.MaxY == height - 1;

    /// <summary>Whether the box leaves at least <paramref name="margin"/> pixels to every edge of the image.</summary>
    public static bool HasMargin(PixelBox box, int margin, int width, int height) =>
        box.MinX >= margin
        && box.MinY >= margin
        && box.MaxX <= width - 1 - margin
        && box.MaxY <= height - 1 - margin;

    /// <summary>
    /// Whether <paramref name="outer"/> grows <paramref name="inner"/> by at
    /// most <paramref name="growth"/> times in width and in height.
    /// </summary>
    public static bool StaysClose(PixelBox outer, PixelBox inner, float growth) =>
        outer.Width <= inner.Width * growth && outer.Height <= inner.Height * growth;

    /// <summary>
    /// The crop that keeps <paramref name="margin"/> pixels around the box.
    /// On a side where the box reaches the edge of the image, something runs
    /// off the frame, so the crop ends at that edge like a photo crop. On the
    /// other sides the crop may reach past the image, which pads it with
    /// transparent pixels.
    /// </summary>
    public static PixelBox MarginCrop(PixelBox box, int margin, int width, int height) =>
        new(
            box.MinX == 0 ? 0 : box.MinX - margin,
            box.MinY == 0 ? 0 : box.MinY - margin,
            box.MaxX == width - 1 ? width - 1 : box.MaxX + margin,
            box.MaxY == height - 1 ? height - 1 : box.MaxY + margin
        );

    /// <summary>The pixels of the crop, as a buffer of its size, transparent where it reaches past the image.</summary>
    public static byte[] Crop(byte[] rgba, int width, int height, PixelBox crop)
    {
        var cropped = new byte[crop.Width * crop.Height * 4];
        int firstX = Math.Max(0, crop.MinX);
        int lastX = Math.Min(width - 1, crop.MaxX);
        if (firstX > lastX)
            return cropped;
        for (int y = Math.Max(0, crop.MinY); y <= Math.Min(height - 1, crop.MaxY); y++)
        {
            Buffer.BlockCopy(
                rgba,
                ((y * width) + firstX) * 4,
                cropped,
                (((y - crop.MinY) * crop.Width) + (firstX - crop.MinX)) * 4,
                (lastX - firstX + 1) * 4
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

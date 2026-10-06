using MapTileCapture.Capture;
using Xunit;

namespace MapTileCapture.Tests.Capture;

public class PortraitImageTests
{
    private static byte[] Pixel(byte r, byte g, byte b, byte a = 255) => [r, g, b, a];

    [Fact]
    public void Matte_KeepsOpaqueColour()
    {
        var matte = PortraitImage.Matte(Pixel(200, 100, 50), Pixel(200, 100, 50));

        Assert.Equal(Pixel(200, 100, 50, 255), matte);
    }

    [Fact]
    public void Matte_ClearsTheBackground()
    {
        var matte = PortraitImage.Matte(Pixel(0, 0, 0), Pixel(255, 255, 255));

        Assert.Equal(Pixel(0, 0, 0, 0), matte);
    }

    [Fact]
    public void Matte_RestoresAnEdgeThatPartlyCoversThePixel()
    {
        // A red edge of 250 over a fifth of the pixel: 50 over black, 50 + 204 over white.
        var matte = PortraitImage.Matte(Pixel(50, 0, 0), Pixel(254, 204, 204));

        Assert.Equal(Pixel(250, 0, 0, 51), matte);
    }

    [Fact]
    public void Matte_GivesAnAdditiveGlowItsBrightnessAsAlpha()
    {
        // An additive glow writes no alpha: it adds 60 over black and saturates over white.
        var matte = PortraitImage.Matte(Pixel(60, 60, 60), Pixel(255, 255, 255));

        Assert.Equal(60, matte[3]);
        Assert.Equal(255, matte[0]);
    }

    [Fact]
    public void Matte_RejectsRendersOfDifferentSizes()
    {
        Assert.Throws<ArgumentException>(() => PortraitImage.Matte(new byte[8], new byte[4]));
    }

    [Fact]
    public void AlphaBox_SpansThePixelsAboveTheThreshold()
    {
        // A 4 x 3 image with opaque pixels at (1, 0) and (2, 2), and a faint one at (3, 1).
        var image = new byte[4 * 3 * 4];
        image[((0 * 4) + 1) * 4 + 3] = 255;
        image[((2 * 4) + 2) * 4 + 3] = 200;
        image[((1 * 4) + 3) * 4 + 3] = 10;

        var box = PortraitImage.AlphaBox(image, 4, 3, 32);

        Assert.NotNull(box);
        Assert.Equal(
            (1, 0, 2, 2),
            (box.Value.MinX, box.Value.MinY, box.Value.MaxX, box.Value.MaxY)
        );
    }

    [Fact]
    public void AlphaBox_IsNullForAnEmptyImage()
    {
        Assert.Null(PortraitImage.AlphaBox(new byte[4 * 4 * 4], 4, 4, 32));
    }

    [Theory]
    [InlineData(0, 3, 5, 6, true)]
    [InlineData(3, 3, 9, 6, true)]
    [InlineData(1, 1, 8, 8, false)]
    public void TouchesBorder_DetectsASubjectAtTheEdge(
        int minX,
        int minY,
        int maxX,
        int maxY,
        bool touches
    )
    {
        Assert.Equal(
            touches,
            PortraitImage.TouchesBorder(new PixelBox(minX, minY, maxX, maxY), 10, 10)
        );
    }

    [Theory]
    [InlineData(5, 5, 94, 94, true)]
    [InlineData(4, 5, 94, 94, false)]
    [InlineData(5, 5, 95, 94, false)]
    public void HasMargin_RequiresTheMarginOnEverySide(
        int minX,
        int minY,
        int maxX,
        int maxY,
        bool fits
    )
    {
        Assert.Equal(
            fits,
            PortraitImage.HasMargin(new PixelBox(minX, minY, maxX, maxY), 5, 100, 100)
        );
    }

    [Fact]
    public void MarginCrop_PadsSidesWhereNothingRunsOffTheFrame()
    {
        var crop = PortraitImage.MarginCrop(new PixelBox(2, 5, 7, 8), 3, 10, 10);

        Assert.Equal((-1, 2, 10, 11), (crop.MinX, crop.MinY, crop.MaxX, crop.MaxY));
    }

    [Fact]
    public void MarginCrop_EndsAtTheEdgeWhereTheSubjectRunsOffTheFrame()
    {
        // An effect reaches the top edge and the right edge of the render.
        var crop = PortraitImage.MarginCrop(new PixelBox(2, 0, 9, 6), 3, 10, 10);

        Assert.Equal((-1, 0, 9, 9), (crop.MinX, crop.MinY, crop.MaxX, crop.MaxY));
    }

    [Fact]
    public void Crop_CopiesTheImageAndLeavesThePaddingTransparent()
    {
        // A 3 x 2 image whose red channel numbers the pixels, all opaque.
        var image = new byte[3 * 2 * 4];
        for (int i = 0; i < 6; i++)
        {
            image[i * 4] = (byte)(i + 1);
            image[(i * 4) + 3] = 255;
        }

        // The crop reaches one pixel past the left edge of the image.
        var cropped = PortraitImage.Crop(image, 3, 2, new PixelBox(-1, 0, 1, 1));

        Assert.Equal(
            new byte[] { 0, 1, 2, 0, 4, 5 },
            new[] { cropped[0], cropped[4], cropped[8], cropped[12], cropped[16], cropped[20] }
        );
        Assert.Equal(0, cropped[3]);
        Assert.Equal(255, cropped[7]);
    }

    [Theory]
    [InlineData(13, 13, true)]
    [InlineData(14, 13, false)]
    [InlineData(13, 14, false)]
    public void StaysClose_LimitsTheGrowthOnBothAxes(int width, int height, bool close)
    {
        var inner = new PixelBox(0, 0, 9, 9);
        var outer = new PixelBox(0, 0, width - 1, height - 1);

        Assert.Equal(close, PortraitImage.StaysClose(outer, inner, 1.35f));
    }

    [Fact]
    public void MeanLuminance_CountsOnlyMostlyOpaquePixels()
    {
        byte[] image =
        [
            .. Pixel(255, 255, 255, 255),
            .. Pixel(0, 0, 0, 255),
            .. Pixel(255, 255, 255, 40),
        ];

        Assert.Equal(0.5, PortraitImage.MeanLuminance(image), 6);
    }
}

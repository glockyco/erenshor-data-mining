using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class ThemeMetricsTests
{
    [Theory]
    [InlineData(0.5f)]
    [InlineData(1f)]
    [InlineData(2f)]
    [InlineData(4f)]
    public void Window_metrics_scale_with_fonts(float scale)
    {
        var m = ThemeMetrics.For(scale);
        Assert.Equal(4f * scale, m.FramePaddingX);
        Assert.Equal(3f * scale, m.FramePaddingY);
        Assert.Equal(8f * scale, m.ItemSpacingX);
        Assert.Equal(4f * scale, m.ItemSpacingY);
        Assert.Equal(16f * scale, m.IndentSpacing);
        Assert.Equal(4f * scale, m.TabRounding);
        Assert.Equal(scale, m.ChildBorderSize);
    }
}

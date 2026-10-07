using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class UiScalePolicyTests
{
    [Theory]
    [InlineData(270f, 0.5f)]
    [InlineData(1080f, 1f)]
    [InlineData(2160f, 2f)]
    [InlineData(8640f, 4f)]
    public void Auto_scale_resolves_screen_height_without_mutating_the_request(
        float height,
        float expected
    )
    {
        float requested = -1f;
        Assert.Equal(expected, UiScalePolicy.Resolve(requested, height));
        Assert.Equal(-1f, requested);
    }

    [Fact]
    public void Manual_scale_ignores_resolution()
    {
        Assert.Equal(1.25f, UiScalePolicy.Resolve(1.25f, 2160));
        Assert.Equal(1.25f, UiScalePolicy.Resolve(1.25f, 540));
    }
}

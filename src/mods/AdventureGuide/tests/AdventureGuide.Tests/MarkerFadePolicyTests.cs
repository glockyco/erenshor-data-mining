using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class MarkerFadePolicyTests
{
    [Theory]
    [InlineData(0f, 1f)]
    [InlineData(60f, 1f)]
    [InlineData(70f, 0.5f)]
    [InlineData(79.99f, 0.0005f)]
    [InlineData(80f, 0f)]
    [InlineData(80.01f, 0f)]
    [InlineData(150f, 0f)]
    public void Subtext_fades_to_zero_at_eighty_metres(float distance, float expected)
    {
        Assert.Equal(expected, MarkerFadePolicy.SubTextAlpha(distance), 4);
        Assert.Equal(expected > 0f, MarkerFadePolicy.ShouldRefreshSubText(distance, 9, 10));
    }

    [Fact]
    public void Hidden_text_keeps_its_old_value_and_refreshes_before_fading_back_in()
    {
        int shown = 100;
        Assert.False(MarkerFadePolicy.ShouldRefreshSubText(100f, 99, shown));
        Assert.False(MarkerFadePolicy.ShouldRefreshSubText(80f, 95, shown));
        Assert.True(MarkerFadePolicy.ShouldRefreshSubText(79.99f, 90, shown));
        shown = 90;
        Assert.False(MarkerFadePolicy.ShouldRefreshSubText(60f, 90, shown));
        Assert.True(MarkerFadePolicy.ShouldRefreshSubText(60f, 89, shown));
    }
}

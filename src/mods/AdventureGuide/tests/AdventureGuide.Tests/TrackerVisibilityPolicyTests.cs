using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class TrackerVisibilityPolicyTests
{
    [Fact]
    public void Menu_transition_suppresses_drawing_without_changing_user_visibility()
    {
        Assert.True(TrackerVisibilityPolicy.ShouldDraw(true, true, true));
        Assert.False(TrackerVisibilityPolicy.ShouldDraw(true, false, true));
        Assert.True(TrackerVisibilityPolicy.ShouldDraw(true, true, true));
        Assert.False(TrackerVisibilityPolicy.ShouldDraw(false, true, true));
        Assert.False(TrackerVisibilityPolicy.ShouldDraw(true, true, false));
    }
}

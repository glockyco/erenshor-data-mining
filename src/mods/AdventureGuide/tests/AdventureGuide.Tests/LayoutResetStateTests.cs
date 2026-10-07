using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class LayoutResetStateTests
{
    [Fact]
    public void Hidden_window_keeps_reset_until_its_next_begin()
    {
        var guide = new LayoutResetState();
        var tracker = new LayoutResetState();
        Assert.False(guide.IsPending(0));
        Assert.True(guide.IsPending(1));
        guide.Applied(1);
        Assert.False(guide.IsPending(1));
        Assert.True(tracker.IsPending(1));
        tracker.Applied(1);
        Assert.False(tracker.IsPending(1));
    }

    [Fact]
    public void Multiple_hidden_resets_coalesce_but_later_resets_still_apply()
    {
        var window = new LayoutResetState();
        Assert.True(window.IsPending(3));
        window.Applied(3);
        Assert.False(window.IsPending(3));
        Assert.True(window.IsPending(4));
    }
}

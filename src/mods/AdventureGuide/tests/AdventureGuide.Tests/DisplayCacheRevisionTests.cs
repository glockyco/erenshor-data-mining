using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class DisplayCacheRevisionTests
{
    [Fact]
    public void Uncommitted_rebuilds_retry_even_when_selection_changes_at_the_same_version()
    {
        var revision = new DisplayCacheRevision();
        Assert.False(revision.IsCurrent(null, 0));
        revision.Commit("quest:a", 3);
        Assert.True(revision.IsCurrent("quest:a", 3));
        Assert.False(revision.IsCurrent("quest:b", 3));
        revision.Invalidate();
        Assert.False(revision.IsCurrent("quest:a", 3));
        Assert.False(revision.IsCurrent("quest:b", 3));
        revision.Commit("quest:b", 3);
        Assert.True(revision.IsCurrent("quest:b", 3));
        Assert.False(revision.IsCurrent("quest:b", 4));
        revision.Commit("quest:b", 4);
        Assert.True(revision.IsCurrent("quest:b", 4));
    }

    [Fact]
    public void No_selection_is_cacheable_only_after_a_successful_clear()
    {
        var revision = new DisplayCacheRevision();
        revision.Commit(null, 5);
        Assert.True(revision.IsCurrent(null, 5));
        Assert.False(revision.IsCurrent("quest:a", 5));
    }
}

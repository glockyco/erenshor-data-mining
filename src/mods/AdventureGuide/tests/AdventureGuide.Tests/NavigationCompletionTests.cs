using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class NavigationCompletionTests
{
    [Theory]
    [InlineData(false, false, false, NavigationCompletionAction.Keep)]
    [InlineData(false, false, true, NavigationCompletionAction.Keep)]
    [InlineData(false, true, true, NavigationCompletionAction.ResolveOrigin)]
    [InlineData(false, true, false, NavigationCompletionAction.Clear)]
    [InlineData(true, false, true, NavigationCompletionAction.Clear)]
    [InlineData(true, true, true, NavigationCompletionAction.Clear)]
    public void Completion_follows_the_origin_not_only_the_resolved_subquest(
        bool originCompleted,
        bool resolvedCompleted,
        bool distinctOrigin,
        NavigationCompletionAction expected
    ) =>
        Assert.Equal(
            expected,
            NavigationCompletionPolicy.Decide(originCompleted, resolvedCompleted, distinctOrigin)
        );

    [Fact]
    public void Subquest_completion_then_parent_completion_returns_then_ends_navigation()
    {
        Assert.Equal(
            NavigationCompletionAction.Keep,
            NavigationCompletionPolicy.Decide(false, false, true)
        );
        Assert.Equal(
            NavigationCompletionAction.ResolveOrigin,
            NavigationCompletionPolicy.Decide(false, true, true)
        );
        Assert.Equal(
            NavigationCompletionAction.Clear,
            NavigationCompletionPolicy.Decide(true, false, true)
        );
    }
}

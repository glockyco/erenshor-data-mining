namespace AdventureGuide.Navigation;

public enum NavigationCompletionAction
{
    Keep,
    Clear,
    ResolveOrigin,
}

public static class NavigationCompletionPolicy
{
    public static NavigationCompletionAction Decide(
        bool originCompleted,
        bool resolvedCompleted,
        bool hasDistinctOrigin
    )
    {
        if (originCompleted)
            return NavigationCompletionAction.Clear;
        if (!resolvedCompleted)
            return NavigationCompletionAction.Keep;
        return hasDistinctOrigin
            ? NavigationCompletionAction.ResolveOrigin
            : NavigationCompletionAction.Clear;
    }
}

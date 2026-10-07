namespace AdventureGuide.UI;

internal struct LayoutResetState
{
    private long _appliedGeneration;

    public readonly bool IsPending(long generation) => generation != _appliedGeneration;

    public void Applied(long generation) => _appliedGeneration = generation;
}

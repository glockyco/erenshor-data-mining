namespace AdventureGuide.Navigation;

/// <summary>Memoizes only the failed scene pair; graph/scene changes invalidate it.</summary>
public sealed class UnroutableRoute
{
    private string? _from;
    private string? _to;

    public bool Matches(string from, string to) =>
        string.Equals(_from, from, StringComparison.OrdinalIgnoreCase)
        && string.Equals(_to, to, StringComparison.OrdinalIgnoreCase);

    public void Remember(string from, string to)
    {
        _from = from;
        _to = to;
    }

    public void Clear()
    {
        _from = null;
        _to = null;
    }
}

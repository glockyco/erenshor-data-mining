namespace AdventureGuide.UI;

internal struct DisplayCacheRevision
{
    private bool _valid;
    private string? _questKey;
    private int _version;

    public readonly bool IsCurrent(string? questKey, int version) =>
        _valid && _questKey == questKey && _version == version;

    public void Invalidate() => _valid = false;

    public void Commit(string? questKey, int version)
    {
        _questKey = questKey;
        _version = version;
        _valid = true;
    }
}

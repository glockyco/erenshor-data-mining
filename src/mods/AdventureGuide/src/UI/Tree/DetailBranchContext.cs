namespace AdventureGuide.UI.Tree;

internal readonly struct DetailBranchContext
{
    private readonly int[] _ancestry;
    private readonly HashSet<int> _forbiddenNodes;

    public DetailBranchContext(int rootQuestIndex, IReadOnlyList<int> ancestry)
    {
        RootQuestIndex = rootQuestIndex;
        _ancestry = ancestry.ToArray();
        _forbiddenNodes = new HashSet<int>(_ancestry);
        ForbiddenFingerprint = ComputeFingerprint(_ancestry);
    }

    private DetailBranchContext(int rootQuestIndex, int[] ancestry)
    {
        RootQuestIndex = rootQuestIndex;
        _ancestry = ancestry;
        _forbiddenNodes = new HashSet<int>(_ancestry);
        ForbiddenFingerprint = ComputeFingerprint(_ancestry);
    }

    public int RootQuestIndex { get; }
    public IReadOnlyList<int> Ancestry => _ancestry;
    public ulong ForbiddenFingerprint { get; }

    public bool Contains(int nodeId) => _forbiddenNodes.Contains(nodeId);

    public bool ContainsBeforeCurrent(int nodeId) =>
        _forbiddenNodes.Contains(nodeId) && (_ancestry.Length == 0 || _ancestry[^1] != nodeId);

    public DetailBranchContext Append(int nodeId)
    {
        if (_ancestry.Length > 0 && _ancestry[^1] == nodeId)
            return this;

        var next = new int[_ancestry.Length + 1];
        Array.Copy(_ancestry, next, _ancestry.Length);
        next[^1] = nodeId;
        return new DetailBranchContext(RootQuestIndex, next);
    }

    public string BuildExactKey() => string.Join(",", _ancestry);

    private static ulong ComputeFingerprint(IReadOnlyList<int> ancestry)
    {
        const ulong offset = 14695981039346656037UL;
        const ulong prime = 1099511628211UL;
        ulong hash = offset;
        for (int i = 0; i < ancestry.Count; i++)
        {
            hash ^= unchecked((uint)ancestry[i]);
            hash *= prime;
        }

        return hash;
    }
}

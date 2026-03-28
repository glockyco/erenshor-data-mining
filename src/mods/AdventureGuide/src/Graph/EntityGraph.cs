namespace AdventureGuide.Graph;

/// <summary>
/// Immutable in-memory entity graph with O(1) node lookup and O(1) adjacency access.
/// Constructed exclusively by <see cref="GraphLoader"/>.
/// </summary>
public sealed class EntityGraph
{
    private static readonly IReadOnlyList<Node> EmptyNodes = Array.Empty<Node>();
    private static readonly IReadOnlyList<Edge> EmptyEdges = Array.Empty<Edge>();

    private readonly Dictionary<string, Node> _nodes;
    private readonly Dictionary<string, List<Edge>> _outEdges;
    private readonly Dictionary<string, List<Edge>> _inEdges;
    private readonly Dictionary<NodeType, IReadOnlyList<Node>> _nodesByType;
    private readonly Dictionary<string, Node> _questsByDbName;
    private readonly int _edgeCount;

    internal EntityGraph(Node[] nodes, Edge[] edges)
    {
        _nodes = new Dictionary<string, Node>(nodes.Length);
        _outEdges = new Dictionary<string, List<Edge>>(nodes.Length);
        _inEdges = new Dictionary<string, List<Edge>>(nodes.Length);
        _edgeCount = edges.Length;

        // Index nodes by key
        foreach (var node in nodes)
            _nodes[node.Key] = node;

        // Index edges by source and target
        foreach (var edge in edges)
        {
            if (!_outEdges.TryGetValue(edge.Source, out var outList))
            {
                outList = new List<Edge>();
                _outEdges[edge.Source] = outList;
            }
            outList.Add(edge);

            if (!_inEdges.TryGetValue(edge.Target, out var inList))
            {
                inList = new List<Edge>();
                _inEdges[edge.Target] = inList;
            }
            inList.Add(edge);
        }

        // Pre-compute nodes grouped by type
        var byType = new Dictionary<NodeType, List<Node>>();
        var questsByDb = new Dictionary<string, Node>(StringComparer.OrdinalIgnoreCase);
        foreach (var node in nodes)
        {
            if (!byType.TryGetValue(node.Type, out var list))
            {
                list = new List<Node>();
                byType[node.Type] = list;
            }
            list.Add(node);

            // Index quest nodes by DB name for fast lookup
            if (node.Type == NodeType.Quest && node.DbName != null)
                questsByDb[node.DbName] = node;
        }

        _nodesByType = new Dictionary<NodeType, IReadOnlyList<Node>>(byType.Count);
        foreach (var (type, list) in byType)
            _nodesByType[type] = list.AsReadOnly();
        _questsByDbName = questsByDb;
    }

    public int NodeCount => _nodes.Count;
    public int EdgeCount => _edgeCount;

    public Node? GetNode(string key) =>
        _nodes.TryGetValue(key, out var node) ? node : null;

    public bool HasNode(string key) => _nodes.ContainsKey(key);

    /// <summary>Look up a quest node by its game DB name (e.g. "ANGLERRING"). O(1).</summary>
    public Node? GetQuestByDbName(string dbName) =>
        _questsByDbName.TryGetValue(dbName, out var node) ? node : null;

    public IReadOnlyList<Node> NodesOfType(NodeType type) =>
        _nodesByType.TryGetValue(type, out var list) ? list : EmptyNodes;

    public IReadOnlyList<Edge> OutEdges(string key) =>
        _outEdges.TryGetValue(key, out var list) ? list : EmptyEdges;

    public IReadOnlyList<Edge> OutEdges(string key, EdgeType type)
    {
        if (!_outEdges.TryGetValue(key, out var all))
            return EmptyEdges;

        var filtered = new List<Edge>();
        foreach (var edge in all)
        {
            if (edge.Type == type)
                filtered.Add(edge);
        }
        return filtered;
    }

    public IReadOnlyList<Edge> InEdges(string key) =>
        _inEdges.TryGetValue(key, out var list) ? list : EmptyEdges;

    public IReadOnlyList<Edge> InEdges(string key, EdgeType type)
    {
        if (!_inEdges.TryGetValue(key, out var all))
            return EmptyEdges;

        var filtered = new List<Edge>();
        foreach (var edge in all)
        {
            if (edge.Type == type)
                filtered.Add(edge);
        }
        return filtered;
    }

    public IEnumerable<Node> AllNodes => _nodes.Values;
    public IEnumerable<Edge> AllEdges
    {
        get
        {
            foreach (var list in _outEdges.Values)
            {
                foreach (var edge in list)
                    yield return edge;
            }
        }
    }
}

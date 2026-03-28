using AdventureGuide.Graph;

namespace AdventureGuide.Navigation;

/// <summary>
/// Maps <see cref="NodeType"/> to an <see cref="IPositionResolver"/>, providing a
/// single entry point that looks up a node by key and delegates to the appropriate resolver.
/// </summary>
public sealed class PositionResolverRegistry
{
    private readonly EntityGraph _graph;
    private readonly Dictionary<NodeType, IPositionResolver> _resolvers = new();

    public PositionResolverRegistry(EntityGraph graph)
    {
        _graph = graph;
    }

    public void Register(NodeType type, IPositionResolver resolver)
    {
        _resolvers[type] = resolver;
    }

    /// <summary>
    /// Resolve world positions for a node key. Appends to the provided results list.
    /// Returns without adding if the node doesn't exist or no resolver is registered.
    /// </summary>
    public void Resolve(string nodeKey, List<ResolvedPosition> results)
    {
        var node = _graph.GetNode(nodeKey);
        if (node == null)
            return;

        if (!_resolvers.TryGetValue(node.Type, out var resolver))
            return;

        resolver.Resolve(node, results);
    }
}

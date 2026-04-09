using AdventureGuide.Graph;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.State;

/// <summary>
/// Central registry that delegates state resolution to per-<see cref="NodeType"/> resolvers.
/// Lazy — resolves state on query, no internal caching.
/// </summary>
public sealed class GameState
{
    private readonly CompiledGuideModel _guide;
    private readonly Dictionary<NodeType, INodeStateResolver> _resolvers = new();

    public GameState(CompiledGuideModel guide)
    {
        _guide = guide;
    }

    /// <summary>Register (or replace) the resolver for a given node type.</summary>
    public void Register(NodeType type, INodeStateResolver resolver)
    {
        _resolvers[type] = resolver;
    }

    /// <summary>
    /// Resolve live state for a node by key. Returns <see cref="NodeState.Unknown"/>
    /// if the node doesn't exist or no resolver is registered for its type.
    /// </summary>
    public NodeState GetState(string nodeKey)
    {
        var node = _guide.GetNode(nodeKey);
        if (node == null)
            return NodeState.Unknown;

        if (!_resolvers.TryGetValue(node.Type, out var resolver))
            return NodeState.Unknown;

        return resolver.Resolve(node);
    }
}

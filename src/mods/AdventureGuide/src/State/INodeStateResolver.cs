using AdventureGuide.Graph;

namespace AdventureGuide.State;

/// <summary>
/// Resolves the live <see cref="NodeState"/> for a single node.
/// One resolver is registered per <see cref="NodeType"/> in <see cref="GameState"/>.
/// </summary>
public interface INodeStateResolver
{
    NodeState Resolve(Node node);
}

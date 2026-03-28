using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves quest node state from the player's quest journal
/// via <see cref="QuestStateTracker"/>.
/// </summary>
public sealed class QuestStateResolver : INodeStateResolver
{
    private readonly QuestStateTracker _tracker;

    public QuestStateResolver(QuestStateTracker tracker)
    {
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        var dbName = node.DbName;
        if (dbName == null)
            return NodeState.Unknown;

        if (_tracker.IsCompleted(dbName))
            return NodeState.Completed;
        if (_tracker.IsActive(dbName))
            return NodeState.Active;
        if (_tracker.IsImplicitlyActive(dbName))
            return NodeState.ImplicitlyActive;

        return NodeState.NotStarted;
    }
}

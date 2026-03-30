using AdventureGuide.Views;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// A resolved world position attributed to both the current actionable goal
/// node and the immediate target node that produced it.
/// Both nodes are <see cref="EntityViewNode"/>s — positions always refer to
/// real game entities, never to synthetic OR-group containers.
/// </summary>
public readonly struct ResolvedViewPosition
{
    public readonly Vector3 Position;
    public readonly string? Scene;
    public readonly string? SourceKey;
    public readonly EntityViewNode GoalNode;
    public readonly EntityViewNode TargetNode;
    public readonly bool IsActionable;

    public ResolvedViewPosition(
        Vector3 position,
        string? scene,
        string? sourceKey,
        EntityViewNode goalNode,
        EntityViewNode targetNode,
        bool isActionable = true)
    {
        Position = position;
        Scene = scene;
        SourceKey = sourceKey;
        GoalNode = goalNode;
        TargetNode = targetNode;
        IsActionable = isActionable;
    }
}

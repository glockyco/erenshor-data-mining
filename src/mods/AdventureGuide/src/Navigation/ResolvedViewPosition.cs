using AdventureGuide.Views;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// A resolved world position attributed to both the current actionable goal
/// node and the immediate target node that produced it.
/// </summary>
public readonly struct ResolvedViewPosition
{
    public readonly Vector3 Position;
    public readonly string? Scene;
    public readonly string? SourceKey;
    public readonly ViewNode GoalNode;
    public readonly ViewNode TargetNode;

    public ResolvedViewPosition(
        Vector3 position,
        string? scene,
        string? sourceKey,
        ViewNode goalNode,
        ViewNode targetNode)
    {
        Position = position;
        Scene = scene;
        SourceKey = sourceKey;
        GoalNode = goalNode;
        TargetNode = targetNode;
    }
}

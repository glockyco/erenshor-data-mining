using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Position;

/// <summary>
/// A resolved world position with its scene name.
/// Scene is required for cross-zone navigation routing.
/// </summary>
public readonly struct ResolvedPosition
{
    public readonly Vector3 Position;
    public readonly string? Scene;
    /// <summary>Key of the graph node that produced this position (e.g., spawn point key). Null for live NPC positions.</summary>
    public readonly string? SourceKey;
    public readonly bool IsActionable;

    public ResolvedPosition(Vector3 position, string? scene, string? sourceKey = null, bool isActionable = true)
    {
        Position = position;
        Scene = scene;
        SourceKey = sourceKey;
        IsActionable = isActionable;
    }
}

/// <summary>
/// Resolves a graph node to zero or more world positions with scene info.
/// Writes results into a caller-provided list to avoid per-call allocation.
/// </summary>
public interface IPositionResolver
{
    void Resolve(Node node, List<ResolvedPosition> results);
}

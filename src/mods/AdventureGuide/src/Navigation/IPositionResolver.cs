using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Navigation;

/// <summary>
/// A resolved world position with its scene name.
/// Scene is required for cross-zone navigation routing.
/// </summary>
public readonly struct ResolvedPosition
{
    public readonly Vector3 Position;
    public readonly string? Scene;

    public ResolvedPosition(Vector3 position, string? scene)
    {
        Position = position;
        Scene = scene;
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

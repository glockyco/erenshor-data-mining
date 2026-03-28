using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves a ZoneLine node to its world position. Currently identical to
/// DirectPositionResolver but registered separately so it can be extended
/// with accessibility filtering (e.g. locked doors, quest gates) without
/// affecting other static-coordinate node types.
/// </summary>
public sealed class ZoneLinePositionResolver : IPositionResolver
{
    public List<ResolvedPosition> Resolve(Node node)
    {
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            return new List<ResolvedPosition> { new ResolvedPosition(new Vector3(node.X.Value, node.Y.Value, node.Z.Value), node.Scene) };
        return new List<ResolvedPosition>();
    }
}

using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves nodes that carry static X/Y/Z coordinates directly on the graph node.
/// Covers: MiningNode, Water, Forge, ItemBag, Door, SpawnPoint, Teleport,
/// AchievementTrigger, SecretPassage, WishingWell, TreasureLocation, WorldObject, ZoneLine.
/// </summary>
public sealed class DirectPositionResolver : IPositionResolver
{
    public List<Vector3> Resolve(Node node)
    {
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            return new List<Vector3> { new Vector3(node.X.Value, node.Y.Value, node.Z.Value) };

        return new List<Vector3>();
    }

    /// <summary>
    /// Registers this resolver for all node types that carry static coordinates.
    /// </summary>
    public static void RegisterAll(PositionResolverRegistry registry)
    {
        var resolver = new DirectPositionResolver();
        var types = new[]
        {
            NodeType.MiningNode,
            NodeType.Water,
            NodeType.Forge,
            NodeType.ItemBag,
            NodeType.Door,
            NodeType.SpawnPoint,
            NodeType.Teleport,
            NodeType.AchievementTrigger,
            NodeType.SecretPassage,
            NodeType.WishingWell,
            NodeType.TreasureLocation,
            NodeType.WorldObject,
            NodeType.ZoneLine,
        };

        foreach (var type in types)
            registry.Register(type, resolver);
    }
}

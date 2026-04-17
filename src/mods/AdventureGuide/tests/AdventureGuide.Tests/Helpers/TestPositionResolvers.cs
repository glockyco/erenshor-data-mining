using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.Position.Resolvers;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

internal static class TestPositionResolvers
{
    public static PositionResolverRegistry Create(
        CompiledGuideModel guide,
        IReadOnlyDictionary<string, bool>? actionabilityByKey = null
    )
    {
        var registry = new PositionResolverRegistry(guide);
        var resolver = new StaticNodePositionResolver(actionabilityByKey);
        registry.Register(NodeType.MiningNode, resolver);
        registry.Register(NodeType.ItemBag, resolver);
        return registry;
    }

    private sealed class StaticNodePositionResolver : IPositionResolver
    {
        private readonly IReadOnlyDictionary<string, bool> _actionabilityByKey;

        public StaticNodePositionResolver(IReadOnlyDictionary<string, bool>? actionabilityByKey)
        {
            _actionabilityByKey =
                actionabilityByKey
                ?? new Dictionary<string, bool>(StringComparer.Ordinal);
        }

        public void Resolve(Node node, List<ResolvedPosition> results)
        {
            if (node.X is null || node.Y is null || node.Z is null)
                return;

            bool isActionable =
                !_actionabilityByKey.TryGetValue(node.Key, out bool actionable)
                || actionable;
            results.Add(
                new ResolvedPosition(
                    node.X.Value,
                    node.Y.Value,
                    node.Z.Value,
                    node.Scene,
                    node.Key,
                    isActionable
                )
            );
        }
    }
}

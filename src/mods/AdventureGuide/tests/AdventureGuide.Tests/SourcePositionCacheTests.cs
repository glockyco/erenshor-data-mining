using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class SourcePositionCacheTests
{
    [Fact]
    public void Resolve_MiningNode_BypassesCache()
    {
        var graph = new TestGraphBuilder()
            .AddMiningNode("mining:test", "Mineral Deposit", scene: "ZoneA")
            .Build();
        var node = graph.GetNode("mining:test")!;
        node.X = 1f;
        node.Y = 2f;
        node.Z = 3f;

        var registry = new PositionResolverRegistry(graph);
        var resolver = new CountingResolver();
        registry.Register(NodeType.MiningNode, resolver);
        var cache = new SourcePositionCache(registry, graph);

        cache.Resolve("mining:test");
        cache.Resolve("mining:test");

        Assert.Equal(2, resolver.CallCount);
    }

    [Fact]
    public void Resolve_StaticSource_UsesCache()
    {
        var graph = new TestGraphBuilder()
            .AddNode("forge:test", NodeType.Forge, "Forge", scene: "ZoneA")
            .Build();
        var node = graph.GetNode("forge:test")!;
        node.X = 1f;
        node.Y = 2f;
        node.Z = 3f;

        var registry = new PositionResolverRegistry(graph);
        var resolver = new CountingResolver();
        registry.Register(NodeType.Forge, resolver);
        var cache = new SourcePositionCache(registry, graph);

        cache.Resolve("forge:test");
        cache.Resolve("forge:test");

        Assert.Equal(1, resolver.CallCount);
    }

    private sealed class CountingResolver : IPositionResolver
    {
        public int CallCount { get; private set; }

        public void Resolve(Node node, List<ResolvedPosition> results)
        {
            CallCount++;
            results.Add(new ResolvedPosition(
                node.X ?? 0f,
                node.Y ?? 0f,
                node.Z ?? 0f,
                node.Scene,
                node.Key));
        }
    }
}

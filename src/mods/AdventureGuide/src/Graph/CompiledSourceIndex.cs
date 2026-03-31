namespace AdventureGuide.Graph;

/// <summary>
/// Pre-compiled source topology indexes built once at startup from <see cref="EntityGraph"/>.
///
/// Two indexes:
/// <list type="number">
///   <item>Item → leaf source nodes: flattened transitive closure through crafting
///     chains, capturing every character/mining-node/water/item-bag/quest that can
///     ultimately provide the item.</item>
///   <item>Source node → static positions: spawn points for characters, direct
///     coordinates for everything else.</item>
/// </list>
///
/// These indexes let target resolution enumerate sources for an item in O(1) lookup
/// instead of recursively walking the view tree.
/// </summary>
public sealed class CompiledSourceIndex
{
    private static readonly IReadOnlyList<SourceEntry> EmptySourceEntries = Array.Empty<SourceEntry>();
    private static readonly IReadOnlyList<StaticSourcePosition> EmptyPositions = Array.Empty<StaticSourcePosition>();

    private readonly Dictionary<string, IReadOnlyList<SourceEntry>> _sourcesByItem;
    private readonly Dictionary<string, IReadOnlyList<StaticSourcePosition>> _positionsBySource;

    public CompiledSourceIndex(EntityGraph graph)
    {
        _positionsBySource = CompileSourcePositions(graph);
        _sourcesByItem = CompileItemSources(graph);
    }

    public IReadOnlyList<SourceEntry> GetSourcesForItem(string itemKey) =>
        _sourcesByItem.TryGetValue(itemKey, out var sources) ? sources : EmptySourceEntries;

    public IReadOnlyList<StaticSourcePosition> GetPositionsForSource(string sourceKey) =>
        _positionsBySource.TryGetValue(sourceKey, out var positions) ? positions : EmptyPositions;

    private static Dictionary<string, IReadOnlyList<StaticSourcePosition>> CompileSourcePositions(EntityGraph graph)
    {
        var result = new Dictionary<string, IReadOnlyList<StaticSourcePosition>>(StringComparer.Ordinal);

        // Characters: collect all spawn point positions
        var characters = graph.NodesOfType(NodeType.Character);
        for (int i = 0; i < characters.Count; i++)
        {
            var charNode = characters[i];
            var spawnEdges = graph.OutEdges(charNode.Key, EdgeType.HasSpawn);
            if (spawnEdges.Count == 0) continue;

            var positions = new List<StaticSourcePosition>();
            for (int j = 0; j < spawnEdges.Count; j++)
            {
                var spawnNode = graph.GetNode(spawnEdges[j].Target);
                if (spawnNode?.X != null && spawnNode.Y != null && spawnNode.Z != null)
                {
                    positions.Add(new StaticSourcePosition(
                        spawnNode.Key, spawnNode.Scene,
                        spawnNode.X.Value, spawnNode.Y.Value, spawnNode.Z.Value));
                }
            }

            if (positions.Count > 0)
                result[charNode.Key] = positions.ToArray();
        }

        // SpawnPoints as direct position sources (e.g. quest giver/completion markers)
        var spawnPoints = graph.NodesOfType(NodeType.SpawnPoint);
        for (int i = 0; i < spawnPoints.Count; i++)
        {
            var sp = spawnPoints[i];
            if (result.ContainsKey(sp.Key)) continue;
            if (sp.X == null || sp.Y == null || sp.Z == null) continue;

            result[sp.Key] = new[] { new StaticSourcePosition(sp.Key, sp.Scene, sp.X.Value, sp.Y.Value, sp.Z.Value) };
        }

        // All other positioned node types
        AddDirectPositionNodes(graph, result, NodeType.MiningNode);
        AddDirectPositionNodes(graph, result, NodeType.Water);
        AddDirectPositionNodes(graph, result, NodeType.Forge);
        AddDirectPositionNodes(graph, result, NodeType.ItemBag);
        AddDirectPositionNodes(graph, result, NodeType.ZoneLine);
        AddDirectPositionNodes(graph, result, NodeType.Door);
        AddDirectPositionNodes(graph, result, NodeType.Teleport);
        AddDirectPositionNodes(graph, result, NodeType.WorldObject);
        AddDirectPositionNodes(graph, result, NodeType.AchievementTrigger);
        AddDirectPositionNodes(graph, result, NodeType.SecretPassage);
        AddDirectPositionNodes(graph, result, NodeType.WishingWell);
        AddDirectPositionNodes(graph, result, NodeType.TreasureLocation);
        AddDirectPositionNodes(graph, result, NodeType.Book);

        return result;
    }

    private static void AddDirectPositionNodes(
        EntityGraph graph,
        Dictionary<string, IReadOnlyList<StaticSourcePosition>> result,
        NodeType type)
    {
        var nodes = graph.NodesOfType(type);
        for (int i = 0; i < nodes.Count; i++)
        {
            var node = nodes[i];
            if (result.ContainsKey(node.Key)) continue;
            if (node.X == null || node.Y == null || node.Z == null) continue;

            result[node.Key] = new[] { new StaticSourcePosition(node.Key, node.Scene, node.X.Value, node.Y.Value, node.Z.Value) };
        }
    }

    private static Dictionary<string, IReadOnlyList<SourceEntry>> CompileItemSources(EntityGraph graph)
    {
        var result = new Dictionary<string, IReadOnlyList<SourceEntry>>(StringComparer.Ordinal);
        var visited = new HashSet<string>(StringComparer.Ordinal);

        var items = graph.NodesOfType(NodeType.Item);
        for (int i = 0; i < items.Count; i++)
        {
            var itemNode = items[i];
            var sources = new List<SourceEntry>();
            visited.Clear();

            CollectItemSources(graph, itemNode.Key, sources, visited);

            if (sources.Count > 0)
                result[itemNode.Key] = sources.ToArray();
        }

        return result;
    }

    private static void CollectItemSources(
        EntityGraph graph,
        string itemKey,
        List<SourceEntry> sources,
        HashSet<string> visited)
    {
        if (!visited.Add(itemKey)) return;

        AddIncomingSources(graph, itemKey, EdgeType.DropsItem, sources);
        AddIncomingSources(graph, itemKey, EdgeType.SellsItem, sources);
        AddIncomingSources(graph, itemKey, EdgeType.GivesItem, sources);
        AddIncomingSources(graph, itemKey, EdgeType.YieldsItem, sources);
        AddIncomingSources(graph, itemKey, EdgeType.RewardsItem, sources);

        // Follow crafting chains: item ← recipe ← materials
        var recipeEdges = graph.OutEdges(itemKey, EdgeType.CraftedFrom);
        for (int i = 0; i < recipeEdges.Count; i++)
        {
            var recipeKey = recipeEdges[i].Target;
            var materialEdges = graph.OutEdges(recipeKey, EdgeType.RequiresMaterial);
            for (int j = 0; j < materialEdges.Count; j++)
            {
                CollectItemSources(graph, materialEdges[j].Target, sources, visited);
            }
        }

        visited.Remove(itemKey);
    }

    private static void AddIncomingSources(
        EntityGraph graph,
        string targetKey,
        EdgeType edgeType,
        List<SourceEntry> sources)
    {
        var edges = graph.InEdges(targetKey, edgeType);
        for (int i = 0; i < edges.Count; i++)
        {
            var sourceNode = graph.GetNode(edges[i].Source);
            if (sourceNode != null)
                sources.Add(new SourceEntry(sourceNode.Key, sourceNode.Type, edgeType));
        }
    }
}

/// <summary>
/// A source node that can provide an item, with the edge type describing
/// how it provides the item (drops, sells, gives, yields, rewards).
/// </summary>
public readonly struct SourceEntry
{
    public readonly string SourceNodeKey;
    public readonly NodeType SourceNodeType;
    public readonly EdgeType AcquisitionEdge;

    public SourceEntry(string sourceNodeKey, NodeType sourceNodeType, EdgeType acquisitionEdge)
    {
        SourceNodeKey = sourceNodeKey;
        SourceNodeType = sourceNodeType;
        AcquisitionEdge = acquisitionEdge;
    }
}

/// <summary>
/// A static world position for a source node, resolved at startup.
/// Characters have one entry per spawn point; other nodes have one entry
/// from their own coordinates.
/// </summary>
public readonly struct StaticSourcePosition
{
    public readonly string PositionNodeKey;
    public readonly string? Scene;
    public readonly float X, Y, Z;

    public StaticSourcePosition(string positionNodeKey, string? scene, float x, float y, float z)
    {
        PositionNodeKey = positionNodeKey;
        Scene = scene;
        X = x; Y = y; Z = z;
    }
}

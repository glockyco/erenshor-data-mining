namespace AdventureGuide.Graph;

/// <summary>
/// Pre-compiled shared source blueprints built once at startup from
/// <see cref="EntityGraph"/>.
///
/// The main product is an immutable item → source-site index. A source site is a
/// canonical source node grouped by acquisition edge and scene, with all static
/// positions in that scene attached. This lets runtime resolution reuse shared
/// item/source structure instead of rediscovering the same world-wide source
/// universe per quest.
/// </summary>
public sealed class CompiledSourceIndex
{
    private static readonly IReadOnlyList<SourceSiteBlueprint> EmptySourceSites = Array.Empty<SourceSiteBlueprint>();
    private static readonly IReadOnlyList<StaticSourcePosition> EmptyPositions = Array.Empty<StaticSourcePosition>();

    private readonly Dictionary<string, IReadOnlyList<SourceSiteBlueprint>> _sourceSitesByItem;
    private readonly Dictionary<string, Dictionary<string, IReadOnlyList<SourceSiteBlueprint>>> _sourceSitesByItemScene;
    private readonly Dictionary<string, IReadOnlyList<StaticSourcePosition>> _positionsBySource;

    public CompiledSourceIndex(EntityGraph graph)
    {
        _positionsBySource = CompileSourcePositions(graph);
        (_sourceSitesByItem, _sourceSitesByItemScene) = CompileItemSourceSites(graph, _positionsBySource);
    }

    public IReadOnlyList<SourceSiteBlueprint> GetSourceSitesForItem(string itemKey) =>
        _sourceSitesByItem.TryGetValue(itemKey, out var sites) ? sites : EmptySourceSites;

    public IReadOnlyList<SourceSiteBlueprint> GetSourceSitesForItemInScene(string itemKey, string scene)
    {
        if (_sourceSitesByItemScene.TryGetValue(itemKey, out var byScene)
            && byScene.TryGetValue(scene, out var sites))
        {
            return sites;
        }

        return EmptySourceSites;
    }

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
            if (spawnEdges.Count == 0)
            {
                if (charNode.X != null && charNode.Y != null && charNode.Z != null)
                {
                    result[charNode.Key] = new[]
                    {
                        new StaticSourcePosition(charNode.Key, charNode.Scene,
                            charNode.X.Value, charNode.Y.Value, charNode.Z.Value),
                    };
                }

                continue;
            }

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

    private static (Dictionary<string, IReadOnlyList<SourceSiteBlueprint>> all, Dictionary<string, Dictionary<string, IReadOnlyList<SourceSiteBlueprint>>> byScene)
        CompileItemSourceSites(
            EntityGraph graph,
            Dictionary<string, IReadOnlyList<StaticSourcePosition>> positionsBySource)
    {
        var all = new Dictionary<string, IReadOnlyList<SourceSiteBlueprint>>(StringComparer.Ordinal);
        var byScene = new Dictionary<string, Dictionary<string, IReadOnlyList<SourceSiteBlueprint>>>(StringComparer.Ordinal);
        var visited = new HashSet<string>(StringComparer.Ordinal);

        var items = graph.NodesOfType(NodeType.Item);
        for (int i = 0; i < items.Count; i++)
        {
            var itemNode = items[i];
            var collector = new SourceSiteCollector(graph, positionsBySource);
            visited.Clear();

            CollectItemSources(graph, itemNode.Key, collector, visited);

            if (collector.SiteCount == 0)
                continue;

            var sites = collector.BuildAll();
            all[itemNode.Key] = sites;
            byScene[itemNode.Key] = collector.BuildByScene();
        }

        return (all, byScene);
    }

    private static void CollectItemSources(
        EntityGraph graph,
        string itemKey,
        SourceSiteCollector collector,
        HashSet<string> visited)
    {
        if (!visited.Add(itemKey))
            return;

        AddIncomingSources(graph, itemKey, EdgeType.DropsItem, collector);
        AddIncomingSources(graph, itemKey, EdgeType.SellsItem, collector);
        AddIncomingSources(graph, itemKey, EdgeType.GivesItem, collector);
        AddIncomingSources(graph, itemKey, EdgeType.YieldsItem, collector);
        AddIncomingSources(graph, itemKey, EdgeType.RewardsItem, collector);

        // Follow crafting chains: item ← recipe ← materials
        var recipeEdges = graph.OutEdges(itemKey, EdgeType.CraftedFrom);
        for (int i = 0; i < recipeEdges.Count; i++)
        {
            var recipeKey = recipeEdges[i].Target;
            var materialEdges = graph.OutEdges(recipeKey, EdgeType.RequiresMaterial);
            for (int j = 0; j < materialEdges.Count; j++)
                CollectItemSources(graph, materialEdges[j].Target, collector, visited);
        }

        visited.Remove(itemKey);
    }

    private static void AddIncomingSources(
        EntityGraph graph,
        string targetKey,
        EdgeType edgeType,
        SourceSiteCollector collector)
    {
        var edges = graph.InEdges(targetKey, edgeType);
        for (int i = 0; i < edges.Count; i++)
        {
            var sourceNode = graph.GetNode(edges[i].Source);
            if (sourceNode != null)
                collector.Add(sourceNode, edgeType);
        }
    }

    private sealed class SourceSiteCollector
    {
        private readonly EntityGraph _graph;
        private readonly Dictionary<string, IReadOnlyList<StaticSourcePosition>> _positionsBySource;
        private readonly Dictionary<string, SourceSiteBuilder> _sites = new(StringComparer.Ordinal);

        public int SiteCount => _sites.Count;

        public SourceSiteCollector(
            EntityGraph graph,
            Dictionary<string, IReadOnlyList<StaticSourcePosition>> positionsBySource)
        {
            _graph = graph;
            _positionsBySource = positionsBySource;
        }

        public void Add(Node sourceNode, EdgeType acquisitionEdge)
        {
            if (_positionsBySource.TryGetValue(sourceNode.Key, out var positions) && positions.Count > 0)
            {
                var byScene = new Dictionary<string, List<StaticSourcePosition>>(StringComparer.OrdinalIgnoreCase);
                for (int i = 0; i < positions.Count; i++)
                {
                    string sceneKey = positions[i].Scene ?? string.Empty;
                    if (!byScene.TryGetValue(sceneKey, out var list))
                    {
                        list = new List<StaticSourcePosition>();
                        byScene[sceneKey] = list;
                    }
                    list.Add(positions[i]);
                }

                foreach (var pair in byScene)
                {
                    AddSite(sourceNode, acquisitionEdge, pair.Key.Length == 0 ? null : pair.Key, pair.Value);
                }

                return;
            }

            AddSite(sourceNode, acquisitionEdge, sourceNode.Scene, positions: null);
        }

        public IReadOnlyList<SourceSiteBlueprint> BuildAll()
        {
            var result = _sites.Values
                .Select(builder => builder.Build())
                .OrderBy(site => site.SourceNodeKey, StringComparer.Ordinal)
                .ThenBy(site => site.Scene, StringComparer.OrdinalIgnoreCase)
                .ThenBy(site => site.AcquisitionEdge)
                .ToArray();
            return result;
        }

        public Dictionary<string, IReadOnlyList<SourceSiteBlueprint>> BuildByScene()
        {
            var result = new Dictionary<string, List<SourceSiteBlueprint>>(StringComparer.OrdinalIgnoreCase);
            foreach (var site in BuildAll())
            {
                if (string.IsNullOrEmpty(site.Scene))
                    continue;

                if (!result.TryGetValue(site.Scene, out var list))
                {
                    list = new List<SourceSiteBlueprint>();
                    result[site.Scene] = list;
                }

                list.Add(site);
            }

            return result.ToDictionary(
                pair => pair.Key,
                pair => (IReadOnlyList<SourceSiteBlueprint>)pair.Value.ToArray(),
                StringComparer.OrdinalIgnoreCase);
        }

        private void AddSite(Node sourceNode, EdgeType acquisitionEdge, string? scene, IReadOnlyList<StaticSourcePosition>? positions)
        {
            string siteId = SourceSiteBlueprint.BuildId(sourceNode.Key, acquisitionEdge, scene);
            if (_sites.TryGetValue(siteId, out var existing))
            {
                existing.AddPositions(positions);
                return;
            }

            var builder = new SourceSiteBuilder(sourceNode, acquisitionEdge, scene);
            builder.AddPositions(positions);
            _sites[siteId] = builder;
        }
    }

    private sealed class SourceSiteBuilder
    {
        private readonly Node _sourceNode;
        private readonly EdgeType _acquisitionEdge;
        private readonly string? _scene;
        private readonly List<StaticSourcePosition> _positions = new();

        public SourceSiteBuilder(Node sourceNode, EdgeType acquisitionEdge, string? scene)
        {
            _sourceNode = sourceNode;
            _acquisitionEdge = acquisitionEdge;
            _scene = scene;
        }

        public void AddPositions(IReadOnlyList<StaticSourcePosition>? positions)
        {
            if (positions == null)
                return;

            for (int i = 0; i < positions.Count; i++)
            {
                if (_positions.Any(existing =>
                    string.Equals(existing.PositionNodeKey, positions[i].PositionNodeKey, StringComparison.Ordinal)))
                {
                    continue;
                }

                _positions.Add(positions[i]);
            }
        }

        public SourceSiteBlueprint Build() =>
            new(
                _sourceNode.Key,
                _sourceNode.Type,
                _acquisitionEdge,
                _scene,
                _positions.Count == 0 ? EmptyPositions : _positions.ToArray());
    }
}

/// <summary>
/// One canonical item source site grouped by acquisition edge and scene.
/// A single character source with spawns in multiple scenes becomes one site per
/// scene; multiple spawns in the same scene share the same site blueprint.
/// </summary>
public readonly struct SourceSiteBlueprint
{
    public readonly string SourceNodeKey;
    public readonly NodeType SourceNodeType;
    public readonly EdgeType AcquisitionEdge;
    public readonly string? Scene;
    public readonly IReadOnlyList<StaticSourcePosition> StaticPositions;

    public SourceSiteBlueprint(
        string sourceNodeKey,
        NodeType sourceNodeType,
        EdgeType acquisitionEdge,
        string? scene,
        IReadOnlyList<StaticSourcePosition> staticPositions)
    {
        SourceNodeKey = sourceNodeKey;
        SourceNodeType = sourceNodeType;
        AcquisitionEdge = acquisitionEdge;
        Scene = scene;
        StaticPositions = staticPositions;
    }

    public static string BuildId(string sourceNodeKey, EdgeType acquisitionEdge, string? scene) =>
        string.Concat(sourceNodeKey, "|", acquisitionEdge, "|", scene ?? string.Empty);
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

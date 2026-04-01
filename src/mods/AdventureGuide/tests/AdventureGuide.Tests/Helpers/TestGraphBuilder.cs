using AdventureGuide.Graph;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Fluent builder for constructing small <see cref="EntityGraph"/> instances in tests.
/// Uses the internal EntityGraph(Node[], Edge[]) constructor exposed via InternalsVisibleTo.
/// </summary>
public sealed class TestGraphBuilder
{
    private readonly List<Node> _nodes = new();
    private readonly List<Edge> _edges = new();

    public TestGraphBuilder AddNode(string key, NodeType type, string displayName,
        string? dbName = null, string? scene = null, string? zone = null,
        string? zoneKey = null, int? level = null, bool implicit_ = false,
        bool repeatable = false, string? keyItemKey = null)
    {
        _nodes.Add(new Node
        {
            Key = key, Type = type, DisplayName = displayName,
            DbName = dbName, Scene = scene, Zone = zone, ZoneKey = zoneKey,
            Level = level, Implicit = implicit_, Repeatable = repeatable,
            KeyItemKey = keyItemKey,
        });
        return this;
    }

    public TestGraphBuilder AddQuest(string key, string name, string? dbName = null,
        string? scene = null, string? zone = null, int? level = null,
        bool implicit_ = false, bool repeatable = false)
        => AddNode(key, NodeType.Quest, name, dbName: dbName, scene: scene,
            zone: zone, level: level, implicit_: implicit_, repeatable: repeatable);

    public TestGraphBuilder AddItem(string key, string name, string? scene = null)
        => AddNode(key, NodeType.Item, name, scene: scene);

    public TestGraphBuilder AddCharacter(string key, string name, string? scene = null,
        string? zone = null, int? level = null)
        => AddNode(key, NodeType.Character, name, scene: scene, zone: zone, level: level);

    public TestGraphBuilder AddDoor(string key, string name, string? scene = null,
        string? keyItemKey = null)
        => AddNode(key, NodeType.Door, name, scene: scene, keyItemKey: keyItemKey);

    public TestGraphBuilder AddZoneLine(string key, string name, string? scene = null,
        string? destinationZoneKey = null)
    {
        _nodes.Add(new Node
        {
            Key = key, Type = NodeType.ZoneLine, DisplayName = name,
            Scene = scene, DestinationZoneKey = destinationZoneKey,
        });
        return this;
    }

    public TestGraphBuilder AddZone(string key, string name, string? scene = null)
        => AddNode(key, NodeType.Zone, name, scene: scene);

    public TestGraphBuilder AddSpawnPoint(string key, string name, string? scene = null,
        string? zone = null)
        => AddNode(key, NodeType.SpawnPoint, name, scene: scene, zone: zone);

    public TestGraphBuilder AddMiningNode(string key, string name, string? scene = null,
        string? zone = null)
        => AddNode(key, NodeType.MiningNode, name, scene: scene, zone: zone);

    public TestGraphBuilder AddItemBag(string key, string name, string? scene = null)
        => AddNode(key, NodeType.ItemBag, name, scene: scene);

    public TestGraphBuilder AddRecipe(string key, string name)
        => AddNode(key, NodeType.Recipe, name);

    public TestGraphBuilder AddEdge(string source, string target, EdgeType type,
        string? group = null, int? ordinal = null, int? quantity = null,
        string? keyword = null, string? note = null)
    {
        _edges.Add(new Edge
        {
            Source = source, Target = target, Type = type,
            Group = group, Ordinal = ordinal, Quantity = quantity,
            Keyword = keyword, Note = note,
        });
        return this;
    }

    public EntityGraph Build() => new(_nodes.ToArray(), _edges.ToArray());
}

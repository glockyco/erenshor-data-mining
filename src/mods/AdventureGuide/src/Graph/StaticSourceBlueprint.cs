namespace AdventureGuide.Graph;

/// <summary>
/// Immutable scene-local static source blueprint derived from graph data.
/// Used for positioned world objects that do not require quest-tree rebuilding
/// to discover their scene membership.
/// </summary>
public sealed class StaticSourceBlueprint
{
    public string NodeKey { get; }
    public string Scene { get; }
    public NodeType NodeType { get; }

    public StaticSourceBlueprint(string nodeKey, string scene, NodeType nodeType)
    {
        NodeKey = nodeKey;
        Scene = scene;
        NodeType = nodeType;
    }
}

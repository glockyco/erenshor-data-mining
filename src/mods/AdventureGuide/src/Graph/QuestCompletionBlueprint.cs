namespace AdventureGuide.Graph;

/// <summary>
/// Immutable quest-completion marker blueprint derived from graph data.
/// </summary>
public sealed class QuestCompletionBlueprint
{
    public string QuestKey { get; }
    public string QuestDbName { get; }
    public string QuestDisplayName { get; }
    public string TargetNodeKey { get; }
    public string PositionNodeKey { get; }
    public string Scene { get; }
    public MarkerInteraction Interaction { get; }
    public bool Repeatable { get; }

    public QuestCompletionBlueprint(
        string questKey,
        string questDbName,
        string questDisplayName,
        string targetNodeKey,
        string positionNodeKey,
        string scene,
        MarkerInteraction interaction,
        bool repeatable
    )
    {
        QuestKey = questKey;
        QuestDbName = questDbName;
        QuestDisplayName = questDisplayName;
        TargetNodeKey = targetNodeKey;
        PositionNodeKey = positionNodeKey;
        Scene = scene;
        Interaction = interaction;
        Repeatable = repeatable;
    }
}

using AdventureGuide.Markers;

namespace AdventureGuide.Graph;

/// <summary>
/// Immutable quest-giver marker blueprint derived from graph data.
/// One quest/character/scene combination may produce multiple blueprints when
/// a character has spawn points in multiple scenes.
/// </summary>
public sealed class QuestGiverBlueprint
{
    public string QuestKey { get; }
    public string QuestDbName { get; }
    public string QuestDisplayName { get; }
    public string CharacterKey { get; }
    public string PositionNodeKey { get; }
    public string Scene { get; }
    public MarkerInteraction Interaction { get; }
    public bool Repeatable { get; }
    public IReadOnlyList<string> RequiredQuestDbNames { get; }

    public QuestGiverBlueprint(
        string questKey,
        string questDbName,
        string questDisplayName,
        string characterKey,
        string positionNodeKey,
        string scene,
        MarkerInteraction interaction,
        bool repeatable,
        IReadOnlyList<string> requiredQuestDbNames)
    {
        QuestKey = questKey;
        QuestDbName = questDbName;
        QuestDisplayName = questDisplayName;
        CharacterKey = characterKey;
        PositionNodeKey = positionNodeKey;
        Scene = scene;
        Interaction = interaction;
        Repeatable = repeatable;
        RequiredQuestDbNames = requiredQuestDbNames;
    }
}

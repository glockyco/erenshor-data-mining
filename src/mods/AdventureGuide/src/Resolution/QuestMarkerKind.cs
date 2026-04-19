namespace AdventureGuide.Resolution;

/// <summary>
/// The quest-semantic marker kind for a resolved action. Set by
/// ResolvedActionSemanticBuilder; consumed by MarkerProjector to configure
/// world marker visuals and by MarkerTextBuilder for label selection.
/// </summary>
public enum QuestMarkerKind
{
    TurnInReady,
    TurnInRepeatReady,
    TurnInPending,
    Objective,
    QuestGiver,
    QuestGiverRepeat,
    QuestGiverBlocked,
}

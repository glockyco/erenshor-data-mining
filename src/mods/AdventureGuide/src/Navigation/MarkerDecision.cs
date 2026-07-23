namespace AdventureGuide.Navigation;

/// <summary>
/// Pure decisions used while collecting world-marker intents.
/// </summary>
public static class MarkerDecision
{
    /// <summary>Choose the marker shown for an available quest giver.</summary>
    public static MarkerType GetQuestGiverType(bool repeatable) =>
        repeatable ? MarkerType.QuestGiverRepeat : MarkerType.QuestGiver;

    /// <summary>
    /// Choose the marker shown for a quest turn-in. A pending turn-in stays
    /// grey regardless of whether the quest is repeatable.
    /// </summary>
    public static MarkerType GetTurnInType(bool hasAllItems, bool repeatable)
    {
        if (!hasAllItems)
            return MarkerType.TurnInPending;

        return repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady;
    }

    /// <summary>
    /// Return true when a candidate intent outranks the marker already stored
    /// for the same spawn key. MarkerType's enum order is the priority order.
    /// </summary>
    public static bool ShouldReplace(MarkerType existing, MarkerType candidate) =>
        candidate < existing;
}

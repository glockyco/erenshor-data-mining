namespace AdventureGuide.Navigation;

/// <summary>What navigation does when the player digs up a treasure.</summary>
internal enum TreasureHuntEndAction
{
    /// <summary>The hunt was not leading navigation.</summary>
    None,

    /// <summary>Return to the step the hunt paused.</summary>
    RestorePaused,

    /// <summary>Follow the selected step again, now without the hunt.</summary>
    ResolveSelection,

    /// <summary>Nothing to return to.</summary>
    Clear,
}

/// <summary>
/// Reading a treasure map points the arrow at the dig site. A selected step
/// whose only sources are treasure chests leads there itself and stays
/// selected. Any other selection is paused and comes back once the player
/// digs. Choosing or clearing navigation during the hunt drops the paused
/// step. The paused step is what gets saved, so it also survives a relog or
/// a character switch during the hunt.
/// </summary>
internal sealed class TreasureHuntNavigation
{
    private string? _pausedQuestKey;
    private int _pausedStepOrder;

    public bool HasPaused => _pausedQuestKey != null;

    /// <summary>Pause the selection; without one there is nothing to return to.</summary>
    public void Pause(string? questKey, int stepOrder)
    {
        if (questKey == null)
            return;
        _pausedQuestKey = questKey;
        _pausedStepOrder = stepOrder;
    }

    public void Drop()
    {
        _pausedQuestKey = null;
        _pausedStepOrder = 0;
    }

    /// <summary>Take the paused step and forget it.</summary>
    public bool TryTakePaused(out string questKey, out int stepOrder)
    {
        questKey = _pausedQuestKey ?? "";
        stepOrder = _pausedStepOrder;
        bool had = _pausedQuestKey != null;
        Drop();
        return had;
    }

    /// <summary>The selection to save: a paused step outlasts the hunt that paused it.</summary>
    public (string QuestKey, int StepOrder) Saved(string? questKey, int stepOrder) =>
        _pausedQuestKey != null ? (_pausedQuestKey, _pausedStepOrder) : (questKey ?? "", stepOrder);

    public TreasureHuntEndAction OnEnded(bool huntLeads, bool hasSelection) =>
        !huntLeads ? TreasureHuntEndAction.None
        : HasPaused ? TreasureHuntEndAction.RestorePaused
        : hasSelection ? TreasureHuntEndAction.ResolveSelection
        : TreasureHuntEndAction.Clear;
}

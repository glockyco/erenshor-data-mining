namespace AdventureGuide.State;

/// <summary>Determines the guide-only status from workflow observations.</summary>
public static class QuestStatusPolicy
{
    /// <summary>
    /// A guide-only quest is available outside its scene, active while its
    /// workflow cycle is in progress, and implicitly active in-scene before
    /// the cycle starts.
    /// </summary>
    public static QuestRuntimeStatus GetGuideOnlyStatus(bool isInCurrentScene, bool isInProgress)
    {
        if (!isInCurrentScene)
            return QuestRuntimeStatus.Available;

        return isInProgress ? QuestRuntimeStatus.Active : QuestRuntimeStatus.ImplicitlyActive;
    }
}

using AdventureGuide.State;

namespace AdventureGuide.Markers;

public readonly struct MarkerChangePlan
{
    public MarkerChangePlan(bool fullRebuild, IReadOnlyCollection<string> affectedQuestKeys)
    {
        FullRebuild = fullRebuild;
        AffectedQuestKeys = affectedQuestKeys;
    }

    public bool FullRebuild { get; }
    public IReadOnlyCollection<string> AffectedQuestKeys { get; }
}

public static class MarkerChangePlanner
{
    public static MarkerChangePlan Plan(GuideChangeSet changeSet)
    {
        if (changeSet == null || !changeSet.HasMeaningfulChanges)
            return new MarkerChangePlan(fullRebuild: false, Array.Empty<string>());

        if (changeSet.SceneChanged || changeSet.LiveWorldChanged)
            return new MarkerChangePlan(fullRebuild: true, Array.Empty<string>());

        return new MarkerChangePlan(fullRebuild: false, changeSet.AffectedQuestKeys);
    }
}

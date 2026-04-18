using AdventureGuide.Diagnostics;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

internal readonly struct MaintainedViewRefreshPlan
{
    public MaintainedViewRefreshPlan(string[] keys, bool preserveUntouchedEntries)
    {
        Keys = keys;
        PreserveUntouchedEntries = preserveUntouchedEntries;
    }

    public string[] Keys { get; }

    public bool PreserveUntouchedEntries { get; }
}

internal static class MaintainedViewRefreshPlanner
{
    public static MaintainedViewRefreshPlan Plan(
        IEnumerable<string> activeKeys,
        GuideChangeSet changeSet,
        DiagnosticTrigger reason
    )
    {
        var activeKeySet = new HashSet<string>(StringComparer.Ordinal);
        foreach (var key in activeKeys)
        {
            if (!string.IsNullOrWhiteSpace(key))
                activeKeySet.Add(key);
        }

        string[] allKeys = activeKeySet.Count == 0 ? Array.Empty<string>() : activeKeySet.ToArray();
        if (allKeys.Length == 0)
            return new MaintainedViewRefreshPlan(allKeys, preserveUntouchedEntries: false);

        if (
            reason is DiagnosticTrigger.NavSetChanged
                or DiagnosticTrigger.TrackedQuestSetChanged
                or DiagnosticTrigger.SceneChanged
        )
            return new MaintainedViewRefreshPlan(allKeys, preserveUntouchedEntries: false);

        if (changeSet.AffectedQuestKeys.Count == 0)
            return new MaintainedViewRefreshPlan(allKeys, preserveUntouchedEntries: false);

        var affected = new List<string>();
        foreach (var key in changeSet.AffectedQuestKeys)
        {
            if (activeKeySet.Contains(key))
                affected.Add(key);
        }

        if (affected.Count == 0 || affected.Count == allKeys.Length)
            return new MaintainedViewRefreshPlan(allKeys, preserveUntouchedEntries: false);

        return new MaintainedViewRefreshPlan(affected.ToArray(), preserveUntouchedEntries: true);
    }
}

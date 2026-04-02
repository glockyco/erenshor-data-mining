using AdventureGuide.Resolution;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

public static class NavigationExplanationBuilder
{
    public static NavigationExplanation Build(
        ResolvedActionSemantic semantic,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode)
    {
        string primary = BuildArrowPrimary(semantic, targetNode);
        string? secondary = BuildArrowSecondary(semantic, primary);
        string? tertiary = BuildArrowTertiary(semantic, secondary);

        return new NavigationExplanation(
            semantic.GoalKind,
            semantic.TargetKind,
            goalNode,
            targetNode,
            primary,
            semantic.TargetIdentityText,
            semantic.ZoneText,
            secondary,
            tertiary);
    }

    public static NavigationExplanation BuildCorpseExplanation(
        ResolvedActionSemantic semantic,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode)
    {
        string payload = semantic.PayloadText ?? semantic.TargetIdentityText;
        string primary = $"Loot {payload}";
        string? secondary = BuildArrowSecondary(semantic, primary);

        return new NavigationExplanation(
            semantic.GoalKind,
            semantic.TargetKind,
            goalNode,
            targetNode,
            primary,
            semantic.TargetIdentityText,
            semantic.ZoneText,
            secondary,
            tertiaryText: null);
    }

    public static TrackerSummary BuildTrackerSummary(
        ResolvedNodeContext frontierNode,
        ResolvedActionSemantic semantic,
        QuestStateTracker tracker,
        int additionalCount,
        string? prerequisiteQuestName = null)
    {
        string primary = BuildTrackerPrimary(semantic, tracker);
        if (additionalCount > 0)
            primary += $" (+{additionalCount} more)";

        string? secondary = BuildTrackerSecondary(frontierNode, semantic, primary, prerequisiteQuestName);
        return new TrackerSummary(primary, secondary);
    }

    private static string BuildArrowPrimary(ResolvedActionSemantic semantic, ResolvedNodeContext targetNode)
    {
        return semantic.ActionKind switch
        {
            ResolvedActionKind.Give when !string.IsNullOrEmpty(semantic.PayloadText)
                => $"Give {semantic.PayloadText}",
            ResolvedActionKind.Buy when !string.IsNullOrEmpty(semantic.PayloadText)
                => $"Buy {semantic.PayloadText}",
            ResolvedActionKind.Talk => $"Talk to {semantic.TargetIdentityText}",
            ResolvedActionKind.SayKeyword => $"Say '{semantic.KeywordText}' to {semantic.TargetIdentityText}",
            ResolvedActionKind.ShoutKeyword => $"Shout '{semantic.KeywordText}' near {semantic.TargetIdentityText}",
            ResolvedActionKind.Kill when targetNode.Quantity is int quantity && quantity > 1
                => $"Kill {semantic.TargetIdentityText} ({quantity})",
            ResolvedActionKind.Kill => $"Kill {semantic.TargetIdentityText}",
            ResolvedActionKind.Read => $"Read {semantic.TargetIdentityText}",
            ResolvedActionKind.Travel => $"Travel to {semantic.TargetIdentityText}",
            ResolvedActionKind.UnlockDoor => $"Unlock {semantic.TargetIdentityText}",
            ResolvedActionKind.Fish => $"Fish at {semantic.TargetIdentityText}",
            ResolvedActionKind.Mine => $"Mine {semantic.TargetIdentityText}",
            ResolvedActionKind.Collect => $"Collect {semantic.TargetIdentityText}",
            ResolvedActionKind.Buy => $"Buy from {semantic.TargetIdentityText}",
            ResolvedActionKind.CompleteQuest => $"Complete {semantic.TargetIdentityText}",
            _ => semantic.TargetIdentityText,
        };
    }

    private static string? BuildArrowSecondary(ResolvedActionSemantic semantic, string primary)
    {
        bool includesTargetIdentity = primary.Contains(semantic.TargetIdentityText, System.StringComparison.OrdinalIgnoreCase);
        if (!includesTargetIdentity)
            return AppendZone(semantic.TargetIdentityText, semantic.ZoneText);

        if (!string.IsNullOrEmpty(semantic.ContextText))
            return AppendZone(semantic.ContextText!, semantic.ZoneText);

        return semantic.ZoneText;
    }

    private static string? BuildArrowTertiary(ResolvedActionSemantic semantic, string? secondary)
    {
        if (string.IsNullOrEmpty(semantic.RationaleText))
            return null;
        if (string.Equals(semantic.RationaleText, secondary, System.StringComparison.OrdinalIgnoreCase))
            return null;
        return semantic.RationaleText;
    }

    private static string BuildTrackerPrimary(ResolvedActionSemantic semantic, QuestStateTracker tracker)
    {
        return semantic.GoalKind switch
        {
            // When the only way to collect an item is to complete a quest (e.g. the
            // quest rewards the item), lead with the quest action, not "Collect X".
            // The rationale "Rewards X" will carry the payload in the secondary line.
            NavigationGoalKind.CollectItem when
                semantic.ActionKind == ResolvedActionKind.CompleteQuest
                => BuildTrackerActionPrimary(semantic),
            NavigationGoalKind.CollectItem => BuildCollectPrimary(semantic, tracker),
            NavigationGoalKind.CompleteBlockingQuest => $"Complete {semantic.TargetIdentityText}",
            _ => BuildTrackerActionPrimary(semantic),
        };
    }

    private static string BuildCollectPrimary(ResolvedActionSemantic semantic, QuestStateTracker tracker)
    {
        string payload = semantic.PayloadText ?? semantic.TargetIdentityText;
        int need = semantic.GoalQuantity ?? 1;
        if (need <= 1 || string.IsNullOrEmpty(semantic.GoalNodeKey))
            return $"Collect {payload}";

        int have = tracker.CountItem(semantic.GoalNodeKey);
        return $"Collect {payload} ({have}/{need})";
    }

    private static string BuildTrackerActionPrimary(ResolvedActionSemantic semantic)
    {
        return semantic.ActionKind switch
        {
            ResolvedActionKind.Give when !string.IsNullOrEmpty(semantic.PayloadText)
                => $"Give {semantic.PayloadText}",
            ResolvedActionKind.Buy when !string.IsNullOrEmpty(semantic.PayloadText)
                => $"Buy {semantic.PayloadText}",
            ResolvedActionKind.Talk => $"Talk to {semantic.TargetIdentityText}",
            ResolvedActionKind.SayKeyword => $"Say '{semantic.KeywordText}' to {semantic.TargetIdentityText}",
            ResolvedActionKind.ShoutKeyword => $"Shout '{semantic.KeywordText}' near {semantic.TargetIdentityText}",
            ResolvedActionKind.Kill => $"Kill {semantic.TargetIdentityText}",
            ResolvedActionKind.Read => $"Read {semantic.TargetIdentityText}",
            ResolvedActionKind.Travel => $"Travel to {semantic.TargetIdentityText}",
            ResolvedActionKind.UnlockDoor => $"Unlock {semantic.TargetIdentityText}",
            ResolvedActionKind.Fish => $"Fish at {semantic.TargetIdentityText}",
            ResolvedActionKind.Mine => $"Mine {semantic.TargetIdentityText}",
            ResolvedActionKind.Collect => $"Collect {semantic.TargetIdentityText}",
            ResolvedActionKind.Buy => $"Buy from {semantic.TargetIdentityText}",
            ResolvedActionKind.CompleteQuest => $"Complete {semantic.TargetIdentityText}",
            _ => semantic.TargetIdentityText,
        };
    }

    private static string? BuildTrackerSecondary(
        ResolvedNodeContext frontierNode,
        ResolvedActionSemantic semantic,
        string primary,
        string? prerequisiteQuestName)
    {
        // Allow RationaleText for CollectItem goals when the action is CompleteQuest
        // (e.g. "Rewards A Rolled Note" when completing a quest yields the needed item).
        // In all other CollectItem cases rationale is suppressed to avoid noise.
        bool rationaleApplies =
            semantic.GoalKind != NavigationGoalKind.CollectItem
            || semantic.ActionKind == ResolvedActionKind.CompleteQuest;

        if (rationaleApplies
            && !string.IsNullOrEmpty(semantic.RationaleText)
            && !string.Equals(semantic.RationaleText, primary, System.StringComparison.OrdinalIgnoreCase))
        {
            return semantic.RationaleText;
        }

        // prerequisiteQuestName (now neededForContext) is the display name of a
        // sub-quest derived from RequiredForQuestKey — the immediate quest within
        // the tracked chain that this target is working toward.
        if (!string.IsNullOrEmpty(prerequisiteQuestName))
        {
            string secondary = $"Needed for {prerequisiteQuestName}";
            return string.Equals(secondary, primary, System.StringComparison.OrdinalIgnoreCase) ? null : secondary;
        }

        if (semantic.GoalKind == NavigationGoalKind.CollectItem)
            return null;

        if (string.Equals(frontierNode.Node.DisplayName, semantic.TargetIdentityText, System.StringComparison.OrdinalIgnoreCase))
            return null;

        string neededFor = $"Needed for {frontierNode.Node.DisplayName}";
        return string.Equals(neededFor, primary, System.StringComparison.OrdinalIgnoreCase) ? null : neededFor;
    }

    private static string AppendZone(string text, string? zoneText) =>
        string.IsNullOrEmpty(zoneText) ? text : $"{text} · {zoneText}";
}
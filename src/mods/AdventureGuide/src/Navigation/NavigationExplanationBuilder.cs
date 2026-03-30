using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

public static class NavigationExplanationBuilder
{
    public static NavigationExplanation Build(
        ResolvedActionSemantic semantic,
        EntityViewNode goalNode,
        EntityViewNode targetNode)
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
        EntityViewNode goalNode,
        EntityViewNode targetNode)
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
        EntityViewNode frontierNode,
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

    private static string BuildArrowPrimary(ResolvedActionSemantic semantic, EntityViewNode targetNode)
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
            ResolvedActionKind.Kill when targetNode.Edge?.Quantity is int quantity && quantity > 1
                => $"Kill {semantic.TargetIdentityText} ({quantity})",
            ResolvedActionKind.Kill => $"Kill {semantic.TargetIdentityText}",
            ResolvedActionKind.Read => $"Read {semantic.TargetIdentityText}",
            ResolvedActionKind.Travel => $"Go to {semantic.TargetIdentityText}",
            ResolvedActionKind.Gather => $"Gather {semantic.TargetIdentityText}",
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
            ResolvedActionKind.Travel => $"Go to {semantic.TargetIdentityText}",
            ResolvedActionKind.Gather => $"Gather {semantic.TargetIdentityText}",
            ResolvedActionKind.Buy => $"Buy from {semantic.TargetIdentityText}",
            ResolvedActionKind.CompleteQuest => $"Complete {semantic.TargetIdentityText}",
            _ => semantic.TargetIdentityText,
        };
    }

    private static string? BuildTrackerSecondary(
        EntityViewNode frontierNode,
        ResolvedActionSemantic semantic,
        string primary,
        string? prerequisiteQuestName)
    {
        if (semantic.GoalKind != NavigationGoalKind.CollectItem
            && !string.IsNullOrEmpty(semantic.RationaleText)
            && !string.Equals(semantic.RationaleText, primary, System.StringComparison.OrdinalIgnoreCase))
        {
            return semantic.RationaleText;
        }

        var blockingQuest = FindBlockingQuest(frontierNode);
        if (blockingQuest != null)
        {
            string secondary = $"Needed for {blockingQuest.Node.DisplayName}";
            return string.Equals(secondary, primary, System.StringComparison.OrdinalIgnoreCase) ? null : secondary;
        }

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

    private static EntityViewNode? FindBlockingQuest(ViewNode node)
    {
        if (node is VariantGroupNode variantGroup)
        {
            // Variant containers have no unlock dependency. Recurse into
            // children to check if item sources are blocked.
            EntityViewNode? firstBlocker = null;
            for (int i = 0; i < variantGroup.Children.Count; i++)
            {
                if (variantGroup.Children[i].IsCycleRef) continue;
                var found = FindBlockingQuest(variantGroup.Children[i]);
                if (found == null) return null;
                firstBlocker ??= found;
            }
            return firstBlocker;
        }

        var entityNode = (EntityViewNode)node;
        if (entityNode.UnlockDependency != null)
            return (EntityViewNode)entityNode.UnlockDependency;

        if (entityNode.Children.Count == 0)
            return null;

        EntityViewNode? firstChildBlocker = null;
        for (int i = 0; i < entityNode.Children.Count; i++)
        {
            var child = entityNode.Children[i];
            if (child.IsCycleRef) continue;
            var found = FindBlockingQuest(child);
            if (found == null) return null;
            firstChildBlocker ??= found;
        }
        return firstChildBlocker;
    }

    private static string AppendZone(string text, string? zoneText) =>
        string.IsNullOrEmpty(zoneText) ? text : $"{text} · {zoneText}";
}

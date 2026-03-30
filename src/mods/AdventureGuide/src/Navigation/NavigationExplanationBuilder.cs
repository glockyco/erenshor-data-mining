using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

/// <summary>
/// Builds semantic navigation explanations from already-resolved pruned view
/// nodes. This is the single place that translates graph/tree semantics into
/// player-facing intent for arrow and tracker surfaces.
/// </summary>
public static class NavigationExplanationBuilder
{
    public static NavigationExplanation Build(
        ViewNode goalNode,
        ViewNode targetNode,
        QuestStateTracker tracker,
        Node? requestedNode = null)
    {
        var goalKind = DetermineGoalKind(goalNode);
        var targetKind = DetermineTargetKind(targetNode);
        string goalText = BuildGoalText(goalNode, tracker, goalKind);
        string targetText = targetNode.Node.DisplayName;
        string? zoneText = GetZoneText(targetNode);
        string? contextText = BuildContextText(requestedNode, goalNode, targetNode);
        string? detailText = BuildDetailText(goalNode, targetNode, goalKind, tracker);

        return new NavigationExplanation(
            goalKind,
            targetKind,
            goalNode,
            targetNode,
            goalText,
            targetText,
            zoneText,
            contextText,
            detailText);
    }

    private static string? BuildContextText(Node? requestedNode, ViewNode goalNode, ViewNode targetNode)
    {
        if (requestedNode?.Type != NodeType.Quest)
            return null;
        if (goalNode.EdgeType != EdgeType.AssignedBy)
            return null;
        if (targetNode.Node.Type != NodeType.Character)
            return null;
        if (string.Equals(requestedNode.DisplayName, targetNode.Node.DisplayName, StringComparison.OrdinalIgnoreCase))
            return null;
        return requestedNode.DisplayName;
    }

    public static TrackerSummary BuildTrackerSummary(
        ViewNode frontierNode,
        ViewNode summaryNode,
        QuestStateTracker tracker,
        int additionalCount)
    {
        var explanation = Build(summaryNode, summaryNode, tracker);
        string primary = explanation.GoalText;

        if (additionalCount > 0)
            primary += $" (+{additionalCount} more)";

        string? secondary = BuildTrackerSecondary(frontierNode, summaryNode);
        return new TrackerSummary(primary, secondary);
    }

    private static string? BuildTrackerSecondary(ViewNode frontierNode, ViewNode summaryNode)
    {
        bool sameSummary = IsSameSummary(frontierNode, summaryNode);
        if (sameSummary)
            return null;

        var blockingQuest = FindBlockingQuest(frontierNode);
        if (blockingQuest != null)
            return $"Needed for {blockingQuest.Node.DisplayName}";

        return $"Needed for {frontierNode.Node.DisplayName}";
    }

    private static bool IsSameSummary(ViewNode frontierNode, ViewNode summaryNode)
    {
        if (frontierNode.EdgeType != summaryNode.EdgeType)
            return false;

        if (frontierNode.NodeKey == summaryNode.NodeKey)
            return true;

        // Position collection can promote a positioned source variant of the same
        // semantic target (for example a directly placed NPC marker node instead of
        // the character node). Suppress redundant secondary text when both summary
        // nodes describe the same visible target.
        return frontierNode.Node.Type == summaryNode.Node.Type
            && string.Equals(
                frontierNode.Node.DisplayName,
                summaryNode.Node.DisplayName,
                StringComparison.OrdinalIgnoreCase);
    }

    private static ViewNode? FindBlockingQuest(ViewNode node)
    {
        if (node.UnlockDependency != null)
            return node.UnlockDependency;

        for (int i = 0; i < node.Children.Count; i++)
        {
            var found = FindBlockingQuest(node.Children[i]);
            if (found != null)
                return found;
        }

        return null;
    }

    private static NavigationGoalKind DetermineGoalKind(ViewNode node)
    {
        if (node.Node.Type == NodeType.Item || node.EdgeType == EdgeType.RequiresItem)
            return NavigationGoalKind.CollectItem;

        return node.EdgeType switch
        {
            EdgeType.StepKill => NavigationGoalKind.KillTarget,
            EdgeType.StepRead => NavigationGoalKind.ReadItem,
            EdgeType.StepTalk or EdgeType.StepShout or EdgeType.AssignedBy => NavigationGoalKind.TalkToTarget,
            EdgeType.StepTravel => NavigationGoalKind.TravelToZone,
            EdgeType.CompletedBy => NavigationGoalKind.CompleteQuest,
            EdgeType.RequiresQuest => NavigationGoalKind.CompleteBlockingQuest,
            _ when node.Node.Type == NodeType.Quest => NavigationGoalKind.CompleteQuest,
            _ => NavigationGoalKind.Generic,
        };
    }

    private static NavigationTargetKind DetermineTargetKind(ViewNode node)
    {
        return node.Node.Type switch
        {
            NodeType.Character => node.EdgeType == EdgeType.StepKill || node.EdgeType == EdgeType.DropsItem
                ? NavigationTargetKind.Enemy
                : NavigationTargetKind.Character,
            NodeType.Item => NavigationTargetKind.Item,
            NodeType.Quest => NavigationTargetKind.Quest,
            NodeType.Zone => NavigationTargetKind.Zone,
            NodeType.ZoneLine => NavigationTargetKind.ZoneLine,
            _ => NavigationTargetKind.Object,
        };
    }

    private static string BuildGoalText(ViewNode node, QuestStateTracker tracker, NavigationGoalKind kind)
    {
        return kind switch
        {
            NavigationGoalKind.CollectItem => FormatCollectItem(node, tracker),
            NavigationGoalKind.CompleteBlockingQuest => $"Complete {node.Node.DisplayName}",
            _ => ActionTextFormatter.FormatSummary(node, tracker),
        };
    }

    private static string FormatCollectItem(ViewNode node, QuestStateTracker tracker)
    {
        string itemName = node.Node.DisplayName;
        int need = node.Edge?.Quantity ?? 1;
        if (need <= 1)
            return $"Collect {itemName}";

        int have = tracker.CountItem(node.NodeKey);
        return $"Collect {itemName} ({have}/{need})";
    }

    private static string? BuildDetailText(
        ViewNode goalNode,
        ViewNode targetNode,
        NavigationGoalKind goalKind,
        QuestStateTracker tracker)
    {
        bool sameTarget = goalNode.NodeKey == targetNode.NodeKey
            && goalNode.EdgeType == targetNode.EdgeType;
        if (sameTarget)
            return null;

        if (goalKind == NavigationGoalKind.CollectItem)
        {
            return targetNode.EdgeType switch
            {
                EdgeType.DropsItem => "Drops the required item",
                EdgeType.SellsItem => "Sells the required item",
                EdgeType.GivesItem => "Gives the required item",
                EdgeType.YieldsItem => "Contains the required item",
                EdgeType.RewardsItem => targetNode.Node.Type == NodeType.Quest
                    ? "Rewards the required item"
                    : "Provides the required item",
                _ => "Unlocks the required source",
            };
        }

        if (goalKind == NavigationGoalKind.CompleteBlockingQuest)
            return "Required for the tracked goal";

        if (targetNode.EdgeType == EdgeType.CompletedBy && goalNode.EdgeType != EdgeType.CompletedBy)
            return "Current completion target";

        if (goalNode.EdgeType == EdgeType.CompletedBy && goalNode.Edge?.Quantity is int qty && qty > 1)
        {
            int have = tracker.CountItem(goalNode.NodeKey);
            return $"Progress {have}/{qty}";
        }

        return null;
    }

    private static string? GetZoneText(ViewNode node)
    {
        if (node.SourceZones != null && node.SourceZones.Count > 0)
        {
            if (node.SourceZones.Count == 1)
                return node.SourceZones[0];
            return string.Join(", ", node.SourceZones);
        }

        return node.Node.Zone;
    }
}

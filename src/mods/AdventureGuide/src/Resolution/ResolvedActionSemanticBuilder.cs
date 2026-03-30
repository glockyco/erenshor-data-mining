using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Views;

namespace AdventureGuide.Resolution;

internal static class ResolvedActionSemanticBuilder
{
    public static ResolvedActionSemantic Build(
        EntityGraph graph,
        Node requestedNode,
        ViewNode goalNode,
        ViewNode targetNode)
    {
        var goalKind = DetermineGoalKind(goalNode);
        var targetKind = DetermineTargetKind(targetNode);
        var actionKind = DetermineActionKind(graph, requestedNode, goalNode, targetNode);
        string? keywordText = goalNode.Edge?.Keyword ?? targetNode.Edge?.Keyword;
        string? payloadText = BuildPayloadText(graph, requestedNode, goalNode, actionKind);
        string targetIdentityText = targetNode.Node.DisplayName;
        string? contextText = BuildContextText(requestedNode, goalNode, targetNode);
        string? rationaleText = BuildRationaleText(goalNode, targetNode, goalKind);
        string? zoneText = GetZoneText(targetNode);
        var markerType = DetermineActiveMarkerType(requestedNode, goalNode);

        return new ResolvedActionSemantic(
            goalKind,
            targetKind,
            actionKind,
            goalNode.NodeKey,
            goalNode.Edge?.Quantity,
            keywordText,
            payloadText,
            targetIdentityText,
            contextText,
            rationaleText,
            zoneText,
            null,
            markerType,
            GetMarkerPriority(markerType));
    }

    public static ResolvedActionSemantic BuildQuestGiver(
        Node quest,
        Node characterNode,
        QuestGiverBlueprint blueprint,
        string? blockedRequirement)
    {
        bool saysKeyword = blueprint.Interaction.Kind == MarkerInteractionKind.SayKeyword
            && !string.IsNullOrEmpty(blueprint.Interaction.Keyword);
        var markerType = blockedRequirement != null
            ? MarkerType.QuestGiverBlocked
            : blueprint.Repeatable ? MarkerType.QuestGiverRepeat : MarkerType.QuestGiver;

        return new ResolvedActionSemantic(
            NavigationGoalKind.StartQuest,
            NavigationTargetKind.Character,
            saysKeyword ? ResolvedActionKind.SayKeyword : ResolvedActionKind.Talk,
            goalNodeKey: null,
            goalQuantity: null,
            blueprint.Interaction.Keyword,
            payloadText: null,
            targetIdentityText: characterNode.DisplayName,
            contextText: quest.DisplayName,
            rationaleText: null,
            zoneText: blueprint.Scene,
            availabilityText: blockedRequirement != null ? $"Requires: {blockedRequirement}" : null,
            preferredMarkerType: markerType,
            markerPriority: GetMarkerPriority(markerType));
    }

    public static ResolvedActionSemantic BuildQuestCompletion(
        EntityGraph graph,
        Node quest,
        Node targetNode,
        QuestCompletionBlueprint blueprint,
        bool ready)
    {
        bool saysKeyword = blueprint.Interaction.Kind == MarkerInteractionKind.SayKeyword
            && !string.IsNullOrEmpty(blueprint.Interaction.Keyword);
        bool hasPayload = HasTurnInPayload(graph, quest);
        var markerType = ready
            ? (quest.Repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady)
            : MarkerType.TurnInPending;

        return new ResolvedActionSemantic(
            NavigationGoalKind.CompleteQuest,
            DetermineTargetKind(targetNode, EdgeType.CompletedBy),
            saysKeyword ? ResolvedActionKind.SayKeyword : hasPayload ? ResolvedActionKind.Give : ResolvedActionKind.Talk,
            goalNodeKey: null,
            goalQuantity: null,
            keywordText: blueprint.Interaction.Keyword,
            payloadText: hasPayload ? FormatTurnInPayload(graph, quest) : null,
            targetIdentityText: targetNode.DisplayName,
            contextText: null,
            rationaleText: null,
            zoneText: blueprint.Scene,
            availabilityText: null,
            preferredMarkerType: markerType,
            markerPriority: GetMarkerPriority(markerType));
    }

    public static int GetMarkerPriority(MarkerType markerType) =>
        markerType switch
        {
            MarkerType.TurnInReady => 10,
            MarkerType.TurnInRepeatReady => 11,
            MarkerType.Objective => 20,
            MarkerType.QuestGiver => 30,
            MarkerType.QuestGiverRepeat => 31,
            MarkerType.QuestGiverBlocked => 40,
            MarkerType.TurnInPending => 25,
            _ => 100,
        };

    private static ResolvedActionKind DetermineActionKind(
        EntityGraph graph,
        Node requestedNode,
        ViewNode goalNode,
        ViewNode targetNode)
    {
        if (IsCompletionTarget(goalNode, targetNode))
        {
            if (!string.IsNullOrEmpty(goalNode.Edge?.Keyword) || !string.IsNullOrEmpty(targetNode.Edge?.Keyword))
                return ResolvedActionKind.SayKeyword;

            return HasTurnInPayload(graph, requestedNode)
                ? ResolvedActionKind.Give
                : ResolvedActionKind.Talk;
        }

        return targetNode.EdgeType switch
        {
            EdgeType.StepTalk or EdgeType.AssignedBy or EdgeType.GivesItem
                when !string.IsNullOrEmpty(targetNode.Edge?.Keyword) => ResolvedActionKind.SayKeyword,
            EdgeType.StepTalk or EdgeType.AssignedBy or EdgeType.GivesItem => ResolvedActionKind.Talk,
            EdgeType.StepShout when !string.IsNullOrEmpty(targetNode.Edge?.Keyword) => ResolvedActionKind.ShoutKeyword,
            EdgeType.StepShout => ResolvedActionKind.Talk,
            EdgeType.StepKill or EdgeType.DropsItem => ResolvedActionKind.Kill,
            EdgeType.StepRead => ResolvedActionKind.Read,
            EdgeType.StepTravel => ResolvedActionKind.Travel,
            EdgeType.SellsItem => ResolvedActionKind.Buy,
            EdgeType.YieldsItem => ResolvedActionKind.Gather,
            EdgeType.RequiresQuest or EdgeType.RewardsItem => ResolvedActionKind.CompleteQuest,
            _ when targetNode.Node.Type == NodeType.Quest => ResolvedActionKind.CompleteQuest,
            _ => ResolvedActionKind.Talk,
        };
    }

    private static string? BuildPayloadText(
        EntityGraph graph,
        Node requestedNode,
        ViewNode goalNode,
        ResolvedActionKind actionKind)
    {
        if (actionKind == ResolvedActionKind.Give)
            return FormatTurnInPayload(graph, requestedNode);

        return DetermineGoalKind(goalNode) == NavigationGoalKind.CollectItem
            ? goalNode.Node.DisplayName
            : null;
    }

    private static string? BuildContextText(Node requestedNode, ViewNode goalNode, ViewNode targetNode)
    {
        if (requestedNode.Type != NodeType.Quest)
            return null;
        if (goalNode.EdgeType != EdgeType.AssignedBy)
            return null;
        if (targetNode.Node.Type != NodeType.Character)
            return null;
        if (string.Equals(requestedNode.DisplayName, targetNode.Node.DisplayName, System.StringComparison.OrdinalIgnoreCase))
            return null;
        return requestedNode.DisplayName;
    }

    private static string? BuildRationaleText(
        ViewNode goalNode,
        ViewNode targetNode,
        NavigationGoalKind goalKind)
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

        return null;
    }

    private static MarkerType DetermineActiveMarkerType(Node requestedNode, ViewNode goalNode) =>
        goalNode.EdgeType == EdgeType.CompletedBy
            ? (requestedNode.Repeatable ? MarkerType.TurnInRepeatReady : MarkerType.TurnInReady)
            : MarkerType.Objective;

    private static bool IsCompletionTarget(ViewNode goalNode, ViewNode targetNode) =>
        goalNode.EdgeType == EdgeType.CompletedBy
        && targetNode.EdgeType == EdgeType.CompletedBy;

    private static bool HasTurnInPayload(EntityGraph graph, Node requestedNode) =>
        requestedNode.Type == NodeType.Quest
        && (graph.OutEdges(requestedNode.Key, EdgeType.RequiresItem).Count > 0
            || graph.OutEdges(requestedNode.Key, EdgeType.RequiresMaterial).Count > 0);

    private static string? FormatTurnInPayload(EntityGraph graph, Node requestedNode)
    {
        if (requestedNode.Type != NodeType.Quest)
            return null;

        var parts = new List<string>();
        CollectPayloadParts(graph, requestedNode.Key, EdgeType.RequiresItem, parts);
        CollectPayloadParts(graph, requestedNode.Key, EdgeType.RequiresMaterial, parts);
        if (parts.Count == 0)
            return null;

        return string.Join(", ", parts);
    }

    private static void CollectPayloadParts(
        EntityGraph graph,
        string questKey,
        EdgeType edgeType,
        List<string> parts)
    {
        var edges = graph.OutEdges(questKey, edgeType);
        for (int i = 0; i < edges.Count; i++)
        {
            var itemNode = graph.GetNode(edges[i].Target);
            if (itemNode == null)
                continue;

            int quantity = edges[i].Quantity ?? 1;
            parts.Add(quantity > 1
                ? $"{itemNode.DisplayName} ({quantity})"
                : itemNode.DisplayName);
        }
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

    private static NavigationTargetKind DetermineTargetKind(ViewNode node) =>
        DetermineTargetKind(node.Node, node.EdgeType);

    private static NavigationTargetKind DetermineTargetKind(Node node, EdgeType? edgeType)
    {
        return node.Type switch
        {
            NodeType.Character => edgeType == EdgeType.StepKill || edgeType == EdgeType.DropsItem
                ? NavigationTargetKind.Enemy
                : NavigationTargetKind.Character,
            NodeType.Item => NavigationTargetKind.Item,
            NodeType.Quest => NavigationTargetKind.Quest,
            NodeType.Zone => NavigationTargetKind.Zone,
            NodeType.ZoneLine => NavigationTargetKind.ZoneLine,
            _ => NavigationTargetKind.Object,
        };
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

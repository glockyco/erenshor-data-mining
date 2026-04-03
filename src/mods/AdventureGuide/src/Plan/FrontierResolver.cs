using AdventureGuide.Graph;
using AdventureGuide.Plan.Semantics;
using AdventureGuide.State;

namespace AdventureGuide.Plan;

/// <summary>
/// Computes actionable frontier refs from a canonical quest plan. This mirrors
/// the current three-phase frontier rules without depending on visual tree shape.
/// </summary>
public static class FrontierResolver
{
    private enum Role
    {
        Done,
        Acceptance,
        Objective,
        Source,
        TurnIn,
        Container,
    }

    public static IReadOnlyList<FrontierRef> ComputeFrontier(QuestPlan plan, GameState state)
    {
        var root = plan.GetNode(plan.RootId)
            ?? throw new InvalidOperationException($"Quest plan root '{plan.RootId}' not found.");
        var frontier = new List<FrontierRef>();
        var seen = new HashSet<PlanNodeId>();
        var questState = root is PlanEntityNode rootEntity
            ? state.GetState(rootEntity.NodeKey)
            : NodeState.Unknown;
        CollectFrontier(plan, root, incomingLink: null, state, questState, frontier, seen);
        return frontier;
    }

    private static void CollectFrontier(
        QuestPlan plan,
        PlanNode node,
        PlanLink? incomingLink,
        GameState state,
        NodeState questState,
        List<FrontierRef> frontier,
        HashSet<PlanNodeId> seen)
    {
        if (node.Status is PlanStatus.PrunedCycle or PlanStatus.PrunedInfeasible)
            return;

        if (node is PlanEntityNode entity && entity.Node.Type == NodeType.Quest)
            questState = state.GetState(entity.NodeKey);

        var role = Classify(node, incomingLink, state, questState);
        switch (role)
        {
            case Role.Done:
            case Role.Source:
                return;

            case Role.Objective:
                AddFrontier(node, incomingLink, frontier, seen);
                return;

            case Role.Acceptance:
            case Role.TurnIn:
                if (node.Outgoing.Count == 0)
                {
                    AddFrontier(node, incomingLink, frontier, seen);
                    return;
                }
                break;

            case Role.Container:
                break;
        }

        List<(PlanNode child, PlanLink link)>? acceptance = null;
        List<(PlanNode child, PlanLink link)>? objectives = null;
        List<(PlanNode child, PlanLink link)>? turnIn = null;

        for (int i = 0; i < node.Outgoing.Count; i++)
        {
            var link = node.Outgoing[i];
            var child = plan.GetNode(link.ToId);
            if (child == null)
                continue;

            var childQuestState = child is PlanEntityNode childEntity && childEntity.Node.Type == NodeType.Quest
                ? state.GetState(childEntity.NodeKey)
                : questState;
            var childRole = Classify(child, link, state, childQuestState);

            switch (childRole)
            {
                case Role.Done:
                case Role.Source:
                    break;
                case Role.Acceptance:
                    acceptance ??= new List<(PlanNode, PlanLink)>();
                    acceptance.Add((child, link));
                    break;
                case Role.TurnIn:
                    turnIn ??= new List<(PlanNode, PlanLink)>();
                    turnIn.Add((child, link));
                    break;
                default:
                    objectives ??= new List<(PlanNode, PlanLink)>();
                    objectives.Add((child, link));
                    break;
            }
        }

        int before = frontier.Count;

        if (acceptance != null)
        {
            for (int i = 0; i < acceptance.Count; i++)
                CollectFrontier(plan, acceptance[i].child, acceptance[i].link, state, questState, frontier, seen);
            if (frontier.Count > before)
                return;
        }

        if (objectives != null)
        {
            for (int i = 0; i < objectives.Count; i++)
                CollectFrontier(plan, objectives[i].child, objectives[i].link, state, questState, frontier, seen);
        }

        if (frontier.Count == before && turnIn != null)
        {
            for (int i = 0; i < turnIn.Count; i++)
                CollectFrontier(plan, turnIn[i].child, turnIn[i].link, state, questState, frontier, seen);
        }

        if (frontier.Count == before && node is PlanEntityNode fallback)
            AddFrontier(fallback, incomingLink, frontier, seen);
    }

    private static Role Classify(PlanNode node, PlanLink? incomingLink, GameState state, NodeState questState)
    {
        if (node is PlanGroupNode)
        {
            if (incomingLink == null)
                return Role.Container;

            return incomingLink.Semantic.Phase switch
            {
                DependencyPhase.Acceptance => Role.Acceptance,
                DependencyPhase.Completion => Role.TurnIn,
                DependencyPhase.Source => Role.Source,
                DependencyPhase.Unlock => Role.Source,
                _ => Role.Container,
            };
        }

        var entity = (PlanEntityNode)node;
        var semantic = incomingLink?.Semantic;

        if (incomingLink == null)
            return questState is QuestCompleted ? Role.Done : Role.Container;

        switch (semantic?.Kind)
        {
            case DependencySemanticKind.AssignmentSource:
                return questState is QuestActive or QuestCompleted or QuestImplicitlyAvailable
                    ? Role.Done : Role.Acceptance;

            case DependencySemanticKind.CompletionTarget:
                return questState is QuestCompleted ? Role.Done : Role.TurnIn;

            case DependencySemanticKind.PrerequisiteQuest:
                return state.GetState(entity.NodeKey) is QuestCompleted ? Role.Done : Role.Container;

            case DependencySemanticKind.RequiredItem:
            case DependencySemanticKind.RequiredMaterial:
                if (questState is QuestCompleted)
                    return Role.Done;
                var requirementState = state.GetState(entity.NodeKey);
                if (requirementState is ItemCount ic && incomingLink.Quantity is int qty)
                    return ic.Count >= qty ? Role.Done : Role.Objective;
                return requirementState.IsSatisfied ? Role.Done : Role.Objective;

            case DependencySemanticKind.StepTalk:
            case DependencySemanticKind.StepKill:
            case DependencySemanticKind.StepTravel:
            case DependencySemanticKind.StepShout:
            case DependencySemanticKind.StepRead:
                return questState is QuestCompleted ? Role.Done : Role.Objective;

            case DependencySemanticKind.ItemSource:
            case DependencySemanticKind.CraftedFrom:
            case DependencySemanticKind.Reward:
            case DependencySemanticKind.UnlockTarget:
                return Role.Source;

            default:
                var ns = state.GetState(entity.NodeKey);
                return ns.IsSatisfied ? Role.Done : Role.Objective;
        }
    }

    private static void AddFrontier(
        PlanNode node,
        PlanLink? incomingLink,
        List<FrontierRef> frontier,
        HashSet<PlanNodeId> seen)
    {
        if (node is not PlanEntityNode entity)
            return;
        if (incomingLink == null)
            return;
        if (!seen.Add(entity.Id))
            return;

        frontier.Add(new FrontierRef(entity.Id, entity.Id, incomingLink));
    }
}
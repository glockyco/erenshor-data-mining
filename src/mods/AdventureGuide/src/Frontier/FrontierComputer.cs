using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Frontier;

/// <summary>
/// Computes the frontier of a quest's dependency tree: the set of all
/// nodes the player can act on right now.
///
/// Every edge in the tree is classified into a role that determines
/// whether its node is skipped, added as a leaf objective, or recursed
/// into. Children are processed in three phases:
///
/// 1. Acceptance — quest acceptance steps (AssignedBy). If any are
///    unsatisfied, they block all other objectives.
/// 2. Objectives — concurrent actionable targets (steps, items).
/// 3. Turn-in — deferred until all objectives are satisfied.
///
/// Sub-quest nodes switch the quest state context so their edges
/// evaluate against the correct quest.
///
/// Pure function of (ViewNode tree, GameState). No state of its own.
/// </summary>
public static class FrontierComputer
{
    /// <summary>
    /// The role of an edge in frontier computation. Each edge type maps
    /// to exactly one role — no ambiguity, no fallback chains.
    /// </summary>
    public enum EdgeRole
    {
        /// <summary>Already satisfied — skip entirely.</summary>
        Done,
        /// <summary>Quest acceptance step — blocks all other objectives.</summary>
        Acceptance,
        /// <summary>A direct player objective — leaf in the frontier.</summary>
        Objective,
        /// <summary>An acquisition source (drop, vendor, etc.) — not an objective.</summary>
        Source,
        /// <summary>Turn-in step — deferred until all objectives are satisfied.</summary>
        TurnIn,
        /// <summary>Contains sub-objectives — recurse into children.</summary>
        Container,
    }

    /// <summary>
    /// Compute frontier ViewNodes from a view tree built by QuestViewBuilder.
    /// Each returned EntityViewNode carries the edge that led to it for formatting.
    /// </summary>
    public static List<EntityViewNode> ComputeFrontier(ViewNode root, GameState state)
    {
        var frontier = new List<EntityViewNode>();
        var seen = new HashSet<string>();
        var questState = state.GetState(root.NodeKey);
        CollectFrontier(root, state, questState, frontier, seen);
        return frontier;
    }

    /// <summary>
    /// Classify an edge into its role for frontier computation. Each edge
    /// type has exactly one rule — the mapping is exhaustive and explicit.
    /// </summary>
    public static EdgeRole ClassifyEdge(ViewNode node, GameState state, NodeState questState)
    {
        // OR-variant containers are transparent to the frontier — recurse into
        // their children, each of which is a RequiresItem objective node.
        if (node is VariantGroupNode)
            return EdgeRole.Container;

        var en = (EntityViewNode)node;

        switch (en.EdgeType)
        {
            // ── Quest lifecycle ────────────────────────────────────
            case null:
                // Root or embedded sub-quest node
                return questState is QuestCompleted ? EdgeRole.Done : EdgeRole.Container;

            case EdgeType.AssignedBy:
                return questState is QuestActive or QuestCompleted or QuestImplicitlyActive
                    ? EdgeRole.Done
                    : EdgeRole.Acceptance;

            case EdgeType.CompletedBy:
                return questState is QuestCompleted ? EdgeRole.Done : EdgeRole.TurnIn;

            // ── Item requirements ──────────────────────────────────
            case EdgeType.RequiresItem:
            case EdgeType.RequiresMaterial:
            {
                if (questState is QuestCompleted)
                    return EdgeRole.Done;
                var ns = state.GetState(en.NodeKey);
                if (ns is ItemCount ic && en.Edge?.Quantity is int qty)
                    return ic.Count >= qty ? EdgeRole.Done : EdgeRole.Objective;
                return ns.IsSatisfied ? EdgeRole.Done : EdgeRole.Objective;
            }

            // ── Quest prerequisites ────────────────────────────────
            case EdgeType.RequiresQuest:
                return state.GetState(en.NodeKey) is QuestCompleted
                    ? EdgeRole.Done : EdgeRole.Container;

            // ── Player action steps ────────────────────────────────
            // The game doesn't expose per-step completion state, so
            // these are always objectives for active quests. When the
            // quest itself is completed, all steps are implicitly done
            // — the game permits completion without individual step
            // tracking.
            case EdgeType.StepTalk:
            case EdgeType.StepKill:
            case EdgeType.StepTravel:
            case EdgeType.StepShout:
            case EdgeType.StepRead:
                return questState is QuestCompleted ? EdgeRole.Done : EdgeRole.Objective;

            // ── Acquisition sources (not objectives) ───────────────
            case EdgeType.DropsItem:
            case EdgeType.SellsItem:
            case EdgeType.GivesItem:
            case EdgeType.YieldsItem:
            case EdgeType.CraftedFrom:
                return EdgeRole.Source;

            case EdgeType.RewardsItem:
                // Quest rewards require completing the quest — recurse.
                // Non-quest rewards are just loot table entries — skip.
                return en.Node.Type == NodeType.Quest
                    ? EdgeRole.Container : EdgeRole.Source;

            // ── Everything else ────────────────────────────────────
            default:
            {
                var ns = state.GetState(en.NodeKey);
                return ns.IsSatisfied ? EdgeRole.Done : EdgeRole.Objective;
            }
        }
    }

    // ── Walker ─────────────────────────────────────────────────────────

    private static void CollectFrontier(
        ViewNode node, GameState state, NodeState questState,
        List<EntityViewNode> frontier, HashSet<string> seen)
    {
        if (node.IsCycleRef) return;

        // Sub-quests carry their own state context.
        // Guard against OR-variant containers, which have no backing Node.
        if (node is EntityViewNode en && en.Node.Type == NodeType.Quest)
            questState = state.GetState(node.NodeKey);


        var role = ClassifyEdge(node, state, questState);

        switch (role)
        {
            case EdgeRole.Done:
            case EdgeRole.Source:
                return;
            case EdgeRole.Objective:
                if (seen.Add(node.NodeKey))
                    frontier.Add((EntityViewNode)node);
                return;
            case EdgeRole.Acceptance:
            case EdgeRole.TurnIn:
                // These are orchestrated by the parent — if we reach here
                // directly (e.g., leaf node), treat as objective.
                if (node.Children.Count == 0)
                {
                    if (seen.Add(node.NodeKey))
                        frontier.Add((EntityViewNode)node);
                    return;
                }
                break;
            case EdgeRole.Container:
                break;
        }

        // ── Three-phase child processing ───────────────────────────

        // Partition children by role.
        List<ViewNode>? acceptance = null;
        List<ViewNode>? objectives = null;
        List<ViewNode>? turnIn = null;

        foreach (var child in node.Children)
        {
            var childQuestState = child is EntityViewNode ce && ce.Node.Type == NodeType.Quest
                ? state.GetState(child.NodeKey) : questState;
            var childRole = ClassifyEdge(child, state, childQuestState);

            switch (childRole)
            {
                case EdgeRole.Done:
                case EdgeRole.Source:
                    break;
                case EdgeRole.Acceptance:
                    acceptance ??= new List<ViewNode>();
                    acceptance.Add(child);
                    break;
                case EdgeRole.TurnIn:
                    turnIn ??= new List<ViewNode>();
                    turnIn.Add(child);
                    break;
                default:
                    objectives ??= new List<ViewNode>();
                    objectives.Add(child);
                    break;
            }
        }

        int before = frontier.Count;

        // Phase 1: Acceptance gates everything else.
        // If the quest hasn't been accepted, only the acceptance step
        // is actionable — other objectives aren't available yet.
        if (acceptance != null)
        {
            foreach (var a in acceptance)
                CollectFrontier(a, state, questState, frontier, seen);
            if (frontier.Count > before)
                return;
        }

        // Phase 2: All objectives are concurrent.
        if (objectives != null)
        {
            foreach (var o in objectives)
                CollectFrontier(o, state, questState, frontier, seen);
        }

        // Phase 3: Turn-in only when all objectives are satisfied.
        if (frontier.Count == before && turnIn != null)
        {
            foreach (var t in turnIn)
            {
                if (seen.Add(t.NodeKey))
                    frontier.Add((EntityViewNode)t);
            }
        }

        // Nothing contributed — this node itself is the frontier.
        // OR-variant containers are structural wrappers with no world position;
        // if all their items are collected the parent quest's turn-in phase
        // handles progression. Never add them to the frontier.
        if (frontier.Count == before && node is EntityViewNode fallback)
        {
            if (seen.Add(fallback.NodeKey))
                frontier.Add(fallback);
        }
    }
}

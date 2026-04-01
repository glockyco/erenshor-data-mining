using AdventureGuide.Graph;

namespace AdventureGuide.Plan.Semantics;

/// <summary>
/// Canonical translation from raw graph edge patterns into shared dependency
/// semantics. All projections should consume this layer instead of pattern-
/// matching raw EdgeType values independently.
/// </summary>
public static class DependencySemantics
{
    public static DependencySemantic FromEdge(EdgeType? edgeType)
    {
        switch (edgeType)
        {
            case null:
                return new DependencySemantic(
                    DependencySemanticKind.QuestRoot,
                    DependencyPhase.None,
                    PlanStructuralKind.Context,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.AssignedBy:
                return new DependencySemantic(
                    DependencySemanticKind.AssignmentSource,
                    DependencyPhase.Acceptance,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.UsuallyFlatten);

            case EdgeType.CompletedBy:
                return new DependencySemantic(
                    DependencySemanticKind.CompletionTarget,
                    DependencyPhase.Completion,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.UsuallyFlatten);

            case EdgeType.RequiresQuest:
                return new DependencySemantic(
                    DependencySemanticKind.PrerequisiteQuest,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.RequiresItem:
                return new DependencySemantic(
                    DependencySemanticKind.RequiredItem,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.RequiresMaterial:
                return new DependencySemantic(
                    DependencySemanticKind.RequiredMaterial,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.UsuallyShow);

            case EdgeType.StepTalk:
                return new DependencySemantic(
                    DependencySemanticKind.StepTalk,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.StepKill:
                return new DependencySemantic(
                    DependencySemanticKind.StepKill,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.StepTravel:
                return new DependencySemantic(
                    DependencySemanticKind.StepTravel,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.StepShout:
                return new DependencySemantic(
                    DependencySemanticKind.StepShout,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.StepRead:
                return new DependencySemantic(
                    DependencySemanticKind.StepRead,
                    DependencyPhase.Objective,
                    PlanStructuralKind.Need,
                    GroupDisplayHint.ProjectionChoice);

            case EdgeType.DropsItem:
            case EdgeType.SellsItem:
            case EdgeType.GivesItem:
            case EdgeType.YieldsItem:
                return new DependencySemantic(
                    DependencySemanticKind.ItemSource,
                    DependencyPhase.Source,
                    PlanStructuralKind.Provide,
                    GroupDisplayHint.UsuallyFlatten);

            case EdgeType.CraftedFrom:
                return new DependencySemantic(
                    DependencySemanticKind.CraftedFrom,
                    DependencyPhase.Source,
                    PlanStructuralKind.Provide,
                    GroupDisplayHint.UsuallyShow);

            case EdgeType.RewardsItem:
                return new DependencySemantic(
                    DependencySemanticKind.Reward,
                    DependencyPhase.Source,
                    PlanStructuralKind.Provide,
                    GroupDisplayHint.UsuallyFlatten);

            case EdgeType.UnlocksCharacter:
            case EdgeType.UnlocksZoneLine:
            case EdgeType.UnlocksDoor:
                return new DependencySemantic(
                    DependencySemanticKind.UnlockTarget,
                    DependencyPhase.Unlock,
                    PlanStructuralKind.Gate,
                    GroupDisplayHint.UsuallyShow);

            default:
                return new DependencySemantic(
                    DependencySemanticKind.Unknown,
                    DependencyPhase.None,
                    PlanStructuralKind.Context,
                    GroupDisplayHint.ProjectionChoice);
        }
    }
}
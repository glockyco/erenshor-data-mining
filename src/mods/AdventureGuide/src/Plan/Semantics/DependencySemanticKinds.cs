namespace AdventureGuide.Plan.Semantics;

/// <summary>Phase semantics shared by all projections.</summary>
public enum DependencyPhase
{
    None,
    Acceptance,
    Objective,
    Completion,
    Source,
    Unlock,
}

/// <summary>
/// Projection hint for whether an explicit canonical group is normally shown or
/// flattened. Projections may override this on a case-by-case basis.
/// </summary>
public enum GroupDisplayHint
{
    ProjectionChoice,
    UsuallyShow,
    UsuallyFlatten,
}

/// <summary>
/// Shared dependency meaning derived from raw graph edge patterns. This is the
/// semantic contract projections consume instead of reinterpreting EdgeType.
/// </summary>
public enum DependencySemanticKind
{
    Unknown,
    QuestRoot,
    AssignmentSource,
    CompletionTarget,
    PrerequisiteQuest,
    RequiredItem,
    RequiredMaterial,
    StepTalk,
    StepKill,
    StepTravel,
    StepShout,
    StepRead,
    ItemSource,
    CraftedFrom,
    Reward,
    UnlockTarget,
}
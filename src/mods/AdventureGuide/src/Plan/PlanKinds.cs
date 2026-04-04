namespace AdventureGuide.Plan;

/// <summary>High-level status assigned by canonical plan analysis.</summary>
public enum PlanStatus
{
    Available,
    Satisfied,
    Blocked,
    PrunedCycle,
    PrunedInfeasible,
}

/// <summary>Structural relation between canonical plan nodes.</summary>
public enum PlanStructuralKind
{
    Need,
    Provide,
    Gate,
    Context,
}

/// <summary>Node kind in the canonical plan graph.</summary>
public enum PlanNodeKind
{
    Entity,
    Group,
}

/// <summary>Explicit logical grouping semantics for sibling dependencies.</summary>
public enum PlanGroupKind
{
    AllOf,
    AnyOf,
    ItemSources,
}
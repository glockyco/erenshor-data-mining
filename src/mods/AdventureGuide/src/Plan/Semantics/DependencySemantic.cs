using AdventureGuide.Plan;

namespace AdventureGuide.Plan.Semantics;

/// <summary>
/// Shared semantic meaning attached to canonical plan links. Keeps projections in
/// sync without forcing UI wording into the structural plan model.
/// </summary>
public sealed class DependencySemantic
{
    public DependencySemanticKind Kind { get; }
    public DependencyPhase Phase { get; }
    public PlanStructuralKind StructuralKind { get; }
    public GroupDisplayHint GroupDisplayHint { get; }

    public DependencySemantic(
        DependencySemanticKind kind,
        DependencyPhase phase,
        PlanStructuralKind structuralKind,
        GroupDisplayHint groupDisplayHint)
    {
        Kind = kind;
        Phase = phase;
        StructuralKind = structuralKind;
        GroupDisplayHint = groupDisplayHint;
    }
}
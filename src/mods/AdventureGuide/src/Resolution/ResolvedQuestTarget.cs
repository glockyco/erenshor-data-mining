using AdventureGuide.Navigation;
using UnityEngine;

namespace AdventureGuide.Resolution;

/// <summary>
/// One resolved actionable world target derived from a quest resolution.
/// The shared semantic action is canonical; arrow and marker projections are
/// derived from it rather than rebuilt locally.
/// </summary>
public sealed class ResolvedQuestTarget
{
    public string TargetNodeKey { get; }
    public string? Scene { get; }
    public string? SourceKey { get; }
    public ResolvedNodeContext GoalNode { get; }
    public ResolvedNodeContext TargetNode { get; }
    public ResolvedActionSemantic Semantic { get; }
    public NavigationExplanation Explanation { get; }

    public Vector3 Position { get; }
    public bool IsActionable { get; }

    public ResolvedQuestTarget(
        string targetNodeKey,
        string? scene,
        string? sourceKey,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode,
        ResolvedActionSemantic semantic,
        NavigationExplanation explanation,
        Vector3 position,
        bool isActionable = true)
    {
        TargetNodeKey = targetNodeKey;
        Scene = scene;
        SourceKey = sourceKey;
        GoalNode = goalNode;
        TargetNode = targetNode;
        Semantic = semantic;
        Explanation = explanation;
        Position = position;
        IsActionable = isActionable;
    }
}

using AdventureGuide.Navigation;
using AdventureGuide.Views;
using UnityEngine;

namespace AdventureGuide.Resolution;

/// <summary>
/// One resolved actionable world target derived from a quest resolution.
/// </summary>
public sealed class ResolvedQuestTarget
{
    public string QuestKey { get; }
    public string TargetNodeKey { get; }
    public string? Scene { get; }
    public string? SourceKey { get; }

    public ViewNode GoalNode { get; }
    public ViewNode TargetNode { get; }
    public NavigationExplanation Explanation { get; }

    public Vector3 Position { get; }
    public MarkerInstruction Marker { get; }

    public ResolvedQuestTarget(
        string questKey,
        string targetNodeKey,
        string? scene,
        string? sourceKey,
        ViewNode goalNode,
        ViewNode targetNode,
        NavigationExplanation explanation,
        Vector3 position,
        MarkerInstruction marker)
    {
        QuestKey = questKey;
        TargetNodeKey = targetNodeKey;
        Scene = scene;
        SourceKey = sourceKey;
        GoalNode = goalNode;
        TargetNode = targetNode;
        Explanation = explanation;
        Position = position;
        Marker = marker;
    }
}

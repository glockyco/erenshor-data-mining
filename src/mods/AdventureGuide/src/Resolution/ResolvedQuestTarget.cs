using AdventureGuide.Navigation;

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

    public float X { get; }
    public float Y { get; }
    public float Z { get; }
    public bool IsActionable { get; }
    /// <summary>
    /// Key of the immediate sub-quest within the tracked chain that this target
    /// is working toward. Null when the target is a direct step of the tracked
    /// quest itself. Used by the tracker to show "Needed for &lt;sub-quest&gt;".
    /// </summary>
    public string? RequiredForQuestKey { get; }

    public ResolvedQuestTarget(
        string targetNodeKey,
        string? scene,
        string? sourceKey,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode,
        ResolvedActionSemantic semantic,
        NavigationExplanation explanation,
        float x,
        float y,
        float z,
        bool isActionable = true,
        string? requiredForQuestKey = null)
    {
        TargetNodeKey      = targetNodeKey;
        Scene              = scene;
        SourceKey          = sourceKey;
        GoalNode           = goalNode;
        TargetNode         = targetNode;
        Semantic           = semantic;
        Explanation        = explanation;
        X                  = x;
        Y                  = y;
        Z                  = z;
        IsActionable       = isActionable;
        RequiredForQuestKey = requiredForQuestKey;
    }
}

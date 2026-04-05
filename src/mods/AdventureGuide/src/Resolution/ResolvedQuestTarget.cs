
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

    // Current world position of the target. Mutable for moving NPCs —
    // NavigationTargetSelector refreshes these each tick before SelectBest.
    public float X { get; internal set; }
    public float Y { get; internal set; }
    public float Z { get; internal set; }
    /// <summary>
    /// Whether this target is currently actionable (alive NPC to kill, lootable
    /// corpse, etc.). Set at resolution time; updated per-frame by
    /// NavigationTargetSelector.UpdateLivePositions for character targets.
    /// </summary>
    public bool IsActionable { get; internal set; }
    /// <summary>
    /// True when this target belongs to a blocked-but-feasible route that must
    /// first resolve some unlock chain before it reaches the original source.
    /// Ranking uses this to prefer easier direct alternatives while still
    /// keeping blocked-feasible paths visible in the resolved set.
    /// </summary>
    public bool IsBlockedPath { get; }
    /// <summary>
    /// True when the item is confirmed present at this target (corpse with confirmed
    /// loot, zone-reentry chest). Navigation prefers these over alive-NPC kill targets
    /// regardless of distance — no kill is required and the item is guaranteed.
    /// </summary>
    public bool IsGuaranteedLoot { get; }
    /// <summary>
    /// Key of the immediate sub-quest within the tracked chain that this target
    /// is working toward. Null when the target is a direct step of the tracked
    /// quest itself. Used by the tracker to show "Needed for {sub-quest}".
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
        string? requiredForQuestKey = null,
        bool isBlockedPath = false,
        bool isGuaranteedLoot = false)
    {
        TargetNodeKey = targetNodeKey;
        Scene = scene;
        SourceKey = sourceKey;
        GoalNode = goalNode;
        TargetNode = targetNode;
        Semantic = semantic;
        Explanation = explanation;
        X = x;
        Y = y;
        Z = z;
        IsActionable = isActionable;
        // Any quest-tagged target is necessarily on a blocked path. The
        // explicit flag additionally covers item/door unlock chains.
        IsBlockedPath = isBlockedPath || requiredForQuestKey != null;
        RequiredForQuestKey = requiredForQuestKey;
        IsGuaranteedLoot = isGuaranteedLoot;
    }
}

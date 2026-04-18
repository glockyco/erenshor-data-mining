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

    /// <summary>
    /// Concrete world-source identity for selection and rendering. Uses the
    /// positioned source node when available so multi-spawn characters do not
    /// collapse to a single conceptual character key.
    /// </summary>
    public string TargetInstanceKey => TargetInstanceIdentity.Get(TargetNodeKey, SourceKey);
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
    /// Canonical rank for source selection. Immediate targets are actionable for the
    /// current goal itself; prerequisite fallbacks only exist because some other
    /// quest/item/unlock chain must be satisfied first.
    /// </summary>
    public ResolvedTargetAvailabilityPriority AvailabilityPriority { get; }

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
    /// Key of the immediate prerequisite quest within the tracked chain that this
    /// target is directly working toward. Null when the target is a direct step of
    /// the tracked quest itself. Used by the tracker to show "Needed for {quest}".
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
        bool isGuaranteedLoot = false,
        ResolvedTargetAvailabilityPriority availabilityPriority = ResolvedTargetAvailabilityPriority.Immediate
    )
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
        AvailabilityPriority = availabilityPriority;
        // Physical route blocking is distinct from quest-chain context. A target can
        // be required for a sub-quest without itself living behind a blocked route.
        IsBlockedPath = isBlockedPath;
        RequiredForQuestKey = requiredForQuestKey;
        IsGuaranteedLoot = isGuaranteedLoot;
    }
}

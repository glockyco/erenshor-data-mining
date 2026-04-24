using AdventureGuide.Resolution;
using AdventureGuide.State;

namespace AdventureGuide.Markers;

/// <summary>
/// Immutable value-type description of a single world marker derived by
/// <see cref="Queries.MarkerCandidatesQuery"/>. Carries only inputs that are
/// static for the current quest/scene/source state; per-frame overlays (live
/// NPC position, respawn timer seconds, night-hour clock) are applied by the
/// projector. Structural equality lets the engine backdate an unchanged list
/// through <see cref="MarkerCandidateList"/>.
/// </summary>
public sealed class MarkerCandidate : IEquatable<MarkerCandidate>
{
    public MarkerCandidate(
        string questKey,
        string targetNodeKey,
        string positionNodeKey,
        string? sourceNodeKey,
        string scene,
        QuestMarkerKind questKind,
        SpawnCategory spawnCategory,
        int priority,
        string subText,
        float x,
        float y,
        float z,
        bool keepWhileCorpsePresent,
        string? corpseSubText,
        bool isNightSpawnNode,
        string displayName,
        string? unlockBlockedReason,
        bool applyLifecycleOverlay = true
    )
    {
        QuestKey = questKey;
        TargetNodeKey = targetNodeKey;
        PositionNodeKey = positionNodeKey;
        SourceNodeKey = sourceNodeKey;
        Scene = scene;
        QuestKind = questKind;
        SpawnCategory = spawnCategory;
        Priority = priority;
        SubText = subText;
        X = x;
        Y = y;
        Z = z;
        KeepWhileCorpsePresent = keepWhileCorpsePresent;
        CorpseSubText = corpseSubText;
        IsNightSpawnNode = isNightSpawnNode;
        DisplayName = displayName;
        UnlockBlockedReason = unlockBlockedReason;
        ApplyLifecycleOverlay = applyLifecycleOverlay;
    }

    public string QuestKey { get; }
    public string TargetNodeKey { get; }
    public string PositionNodeKey { get; }
    public string? SourceNodeKey { get; }
    public string Scene { get; }
    public QuestMarkerKind QuestKind { get; }
    public SpawnCategory SpawnCategory { get; }
    public int Priority { get; }
    public string SubText { get; }
    public float X { get; }
    public float Y { get; }
    public float Z { get; }
    public bool KeepWhileCorpsePresent { get; }
    public string? CorpseSubText { get; }
    public bool IsNightSpawnNode { get; }
    public string DisplayName { get; }
    public string? UnlockBlockedReason { get; }

    public bool ApplyLifecycleOverlay { get; }

    public bool Equals(MarkerCandidate? other)
    {
        if (other is null)
            return false;
        if (ReferenceEquals(this, other))
            return true;
        return QuestKey == other.QuestKey
            && TargetNodeKey == other.TargetNodeKey
            && PositionNodeKey == other.PositionNodeKey
            && SourceNodeKey == other.SourceNodeKey
            && Scene == other.Scene
            && QuestKind == other.QuestKind
            && SpawnCategory == other.SpawnCategory
            && Priority == other.Priority
            && SubText == other.SubText
            && X.Equals(other.X)
            && Y.Equals(other.Y)
            && Z.Equals(other.Z)
            && KeepWhileCorpsePresent == other.KeepWhileCorpsePresent
            && CorpseSubText == other.CorpseSubText
            && IsNightSpawnNode == other.IsNightSpawnNode
            && DisplayName == other.DisplayName
            && UnlockBlockedReason == other.UnlockBlockedReason
            && ApplyLifecycleOverlay == other.ApplyLifecycleOverlay;
    }

    public override bool Equals(object? obj) => Equals(obj as MarkerCandidate);

    public override int GetHashCode()
    {
        var first = HashCode.Combine(
            QuestKey,
            TargetNodeKey,
            PositionNodeKey,
            SourceNodeKey,
            Scene,
            QuestKind,
            SpawnCategory,
            Priority
        );
        var second = HashCode.Combine(
            SubText,
            X,
            Y,
            Z,
            KeepWhileCorpsePresent,
            CorpseSubText,
            IsNightSpawnNode
        );
        var third = HashCode.Combine(DisplayName, UnlockBlockedReason, ApplyLifecycleOverlay);
        return HashCode.Combine(first, second, third);
    }
}

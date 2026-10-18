#nullable enable

using SQLite;

/// <summary>
/// One atom of a quest listener's effect on a scene subject. Groups are OR
/// alternatives and the atoms of a group are required together. Enable and
/// disable effects are separate, because disabling wins when both fire.
/// </summary>
[Table("QuestActivationEffects")]
public sealed class QuestActivationEffectRecord
{
    [PrimaryKey]
    public string RecordKey { get; set; } = "";
    public string ListenerKey { get; set; } = "";
    public string ListenerObjectKey { get; set; } = "";
    public bool ListenerComponentIsEnabled { get; set; }
    public string Script { get; set; } = "";
    public string Scene { get; set; } = "";
    public bool ListenerIsEnabled { get; set; }
    public string TargetObjectKey { get; set; } = "";
    public string TargetObjectName { get; set; } = "";
    public string TargetKind { get; set; } = "";
    public string TargetStableKey { get; set; } = "";
    public bool TargetIsEnabled { get; set; }
    public string Effect { get; set; } = "";
    public int GroupIndex { get; set; }
    public string AtomKind { get; set; } = "";
    public string AtomStableKey { get; set; } = "";
}

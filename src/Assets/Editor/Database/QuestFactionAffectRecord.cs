#nullable enable

using SQLite;

[Table("QuestFactionAffects")]
public class QuestFactionAffectRecord
{
    public const string TableName = "QuestFactionAffects";

    [Indexed(Name = "QuestFactionAffects_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(QuestVariantRecord), "ResourceName")]
    public string QuestVariantResourceName { get; set; } = string.Empty;

    [Indexed(Name = "QuestFactionAffects_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(WorldFactionRecord), "StableKey")]
    public string FactionStableKey { get; set; } = string.Empty;

    public int ModifierValue { get; set; }
}

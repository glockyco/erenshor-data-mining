#nullable enable

using SQLite;

[Table("QuestFactionAffects")]
public class QuestFactionAffectRecord
{
    public const string TableName = "QuestFactionAffects";

    [Indexed(Name = "QuestFactionAffects_Primary_IDX", Order = 1, Unique = true)]
    public int QuestId { get; set; }

    [Indexed(Name = "QuestFactionAffects_Primary_IDX", Order = 2, Unique = true)]
    public string FactionREFNAME { get; set; } = string.Empty;

    public int ModifierValue { get; set; }
}

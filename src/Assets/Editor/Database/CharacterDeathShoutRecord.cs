#nullable enable

using SQLite;

[Table("CharacterDeathShouts")]
public class CharacterDeathShoutRecord
{
    public const string TableName = "CharacterDeathShouts";

    [Indexed(Name = "CharacterDeathShouts_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterDeathShouts_Primary_IDX", Order = 2, Unique = true)]
    public int SequenceIndex { get; set; }

    public string ShoutText { get; set; } = string.Empty;
}

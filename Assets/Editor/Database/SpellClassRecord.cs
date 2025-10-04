#nullable enable

using SQLite;

[Table("SpellClasses")]
public class SpellClassRecord
{
    public const string TableName = "SpellClasses";

    [Indexed(Name = "SpellClasses_Primary_IDX", Order = 1, Unique = true)]
    public int SpellId { get; set; }

    [Indexed(Name = "SpellClasses_Primary_IDX", Order = 2, Unique = true)]
    public string ClassName { get; set; } = string.Empty;
}

#nullable enable

using SQLite;

[Table("CharacterDamageReleaseRules")]
public sealed class CharacterDamageReleaseRecord
{
    [PrimaryKey]
    public string RuleKey { get; set; } = "";
    public string CharacterStableKey { get; set; } = "";
    public string Mechanism { get; set; } = "";
    public string SourceStableKey { get; set; } = "";
    public string ConditionKind { get; set; } = "";
    public string? ConditionStableKey { get; set; }
    public bool CanRelease { get; set; }
    public bool ControllerEnabled { get; set; }
}

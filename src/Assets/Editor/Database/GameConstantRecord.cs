#nullable enable

using SQLite;

/// <summary>
/// Stores game constants extracted from GameData.cs static fields.
/// These values affect game mechanics like NPC HP scaling, XP rates, etc.
/// </summary>
[Table("GameConstants")]
public class GameConstantRecord
{
    public const string TableName = "GameConstants";

    /// <summary>
    /// The constant name (e.g., "HPScale", "ServerXPMod")
    /// </summary>
    [PrimaryKey]
    public string Key { get; set; } = string.Empty;

    /// <summary>
    /// The constant value as a string
    /// </summary>
    public string Value { get; set; } = string.Empty;

    /// <summary>
    /// The data type: "float", "int", "bool", "string"
    /// </summary>
    public string ValueType { get; set; } = string.Empty;

    /// <summary>
    /// Optional description of what this constant does
    /// </summary>
    public string? Description { get; set; }
}

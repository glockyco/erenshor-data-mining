#nullable enable

using SQLite;

/// <summary>
/// One Item field of a placed Chessboard component: a figurine that summons a
/// game piece, or the mold that replaces the Candlekeeper figurine.
/// </summary>
[Table("ChessboardItems")]
public class ChessboardItemRecord
{
    [Indexed(Name = "ChessboardItems_Primary_IDX", Order = 1, Unique = true)]
    public string Scene { get; set; } = string.Empty;

    /// <summary>The serialized field name, for example "Candlekeeper" or "ReplaceStatue".</summary>
    [Indexed(Name = "ChessboardItems_Primary_IDX", Order = 2, Unique = true)]
    public string Field { get; set; } = string.Empty;

    /// <summary>The item, or null when the field is empty.</summary>
    public string? ItemStableKey { get; set; }
}

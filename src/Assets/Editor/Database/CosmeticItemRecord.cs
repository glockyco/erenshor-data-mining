#nullable enable

using SQLite;

/// <summary>
/// An item that the player's <c>Inventory</c> names for a cosmetic slot effect. While a
/// cosmetic slot holds the item, <c>Inventory.Update</c> keeps the game object of
/// <see cref="Effect"/> on: the belt lamp for the Belt Lamp, the Shivering Belt Lamp,
/// and the Keeper's Lantern, and the lens for the Watcher's Lens.
/// </summary>
[Table("CosmeticItems")]
public class CosmeticItemRecord
{
    [PrimaryKey]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string ItemStableKey { get; set; } = string.Empty;

    /// <summary>The <c>Inventory</c> field of the game object: "BeltLamp" or "FernallanLensObj".</summary>
    public string Effect { get; set; } = string.Empty;

    /// <summary>The <c>Inventory</c> field that names the item, such as "KeepersLamp".</summary>
    public string Field { get; set; } = string.Empty;
}

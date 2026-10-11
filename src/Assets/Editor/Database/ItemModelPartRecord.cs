#nullable enable

using SQLite;

/// <summary>
/// One descendant of a slot transform of the player's male or female body. Equipping an
/// item turns on the descendants whose name is the item's <c>EquipmentToActivate</c>, so
/// these rows say which parts each body holds for an item and which meshes they draw.
/// </summary>
[Table("ItemModelParts")]
public class ItemModelPartRecord
{
    /// <summary>The body whose <c>ModularParts</c> names the slot: "Male" or "Female".</summary>
    [Indexed(Name = "ItemModelParts_Primary_IDX", Order = 1, Unique = true)]
    public string Body { get; set; } = string.Empty;

    /// <summary>
    /// The <c>ModularParts</c> field of the slot transform, such as "Chest" or "BootsL",
    /// or "HalloweenMasks" for the mask objects.
    /// </summary>
    [Indexed(Name = "ItemModelParts_Primary_IDX", Order = 2, Unique = true)]
    public string Slot { get; set; } = string.Empty;

    /// <summary>The part's index among the slot's descendants, or its index in the mask list.</summary>
    [Indexed(Name = "ItemModelParts_Primary_IDX", Order = 3, Unique = true)]
    public int Position { get; set; }

    /// <summary>The part's name, which an item names in <c>EquipmentToActivate</c>.</summary>
    public string Part { get; set; } = string.Empty;

    /// <summary>
    /// The meshes that the part and its descendants draw, as sorted
    /// "asset path:mesh name" entries joined by "|", or empty when it draws none.
    /// </summary>
    public string Meshes { get; set; } = string.Empty;
}

/// <summary>
/// One furnishing of a Reliquary planning table slot. Building the slot turns on the
/// child whose name is the furniture item's <c>EquipmentToActivate</c>.
/// </summary>
[Table("PlanningTableFurnishings")]
public class PlanningTableFurnishingRecord
{
    [Indexed(Name = "PlanningTableFurnishings_Primary_IDX", Order = 1, Unique = true)]
    public string Scene { get; set; } = string.Empty;

    [Indexed(Name = "PlanningTableFurnishings_Primary_IDX", Order = 2, Unique = true)]
    public string Slot { get; set; } = string.Empty;

    [Indexed(Name = "PlanningTableFurnishings_Primary_IDX", Order = 3, Unique = true)]
    public string Furnishing { get; set; } = string.Empty;

    /// <summary>The renderers under the furnishing, active or not.</summary>
    public int RendererCount { get; set; }
}

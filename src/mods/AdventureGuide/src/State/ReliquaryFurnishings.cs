using AdventureGuide.Data;

namespace AdventureGuide.State;

/// <summary>
/// The room furnishings, planar stones and runes stored in the Reliquary planning table.
/// The game loads the table at login, so availability is known in every zone.
/// </summary>
public sealed class ReliquaryFurnishings : IFurnitureSlots
{
    private readonly Item?[] _items = new Item?[
        FurnishingPolicy.RoomSlots.Length
            + FurnishingPolicy.PlanarSlots.Length
            + FurnishingPolicy.RuneSlots.Length
    ];
    private readonly string?[] _keys = new string?[
        FurnishingPolicy.RoomSlots.Length
            + FurnishingPolicy.PlanarSlots.Length
            + FurnishingPolicy.RuneSlots.Length
    ];

    /// <summary>
    /// Re-read stored slots. Returns true when a slot changes.
    /// Reference checks only, so it runs every frame without allocation.
    /// </summary>
    public bool Poll()
    {
        var table = GameData.PlanningUI;
        bool changed = false;
        for (int i = 0; i < _items.Length; i++)
        {
            var item = table != null ? SlotIcon(table, i)?.MyItem : null;
            if (ReferenceEquals(item, _items[i]))
                continue;
            _items[i] = item;
            _keys[i] = KeyOf(item);
            changed = true;
        }
        return changed;
    }

    public string? ItemKeyIn(string slot)
    {
        int index = Array.IndexOf(FurnishingPolicy.RoomSlots, slot);
        if (index >= 0)
            return _keys[index];
        index = Array.IndexOf(FurnishingPolicy.PlanarSlots, slot);
        if (index >= 0)
            return _keys[FurnishingPolicy.RoomSlots.Length + index];
        index = Array.IndexOf(FurnishingPolicy.RuneSlots, slot);
        return index >= 0
            ? _keys[FurnishingPolicy.RoomSlots.Length + FurnishingPolicy.PlanarSlots.Length + index]
            : null;
    }

    private static string? KeyOf(Item? item)
    {
        if (item == null || (GameData.PlayerInv != null && item == GameData.PlayerInv.Empty))
            return null;
        return "item:" + item.name.Trim().ToLowerInvariant();
    }

    // RoomSlots followed by PlanarSlots and RuneSlots.
    private static ItemIcon? SlotIcon(PlanningTableUI table, int index) =>
        index switch
        {
            0 => table.L1,
            1 => table.L2,
            2 => table.L3,
            3 => table.L4,
            4 => table.R1,
            5 => table.R2,
            6 => table.R3,
            7 => table.R4,
            8 => table.PlanarFern,
            9 => table.PlanarBrax,
            10 => table.PlanarVith,
            11 => table.PlanarSol,
            12 => table.Rune1,
            13 => table.Rune2,
            14 => table.Rune3,
            15 => table.Rune4,
            16 => table.Rune5,
            17 => table.Rune6,
            _ => null,
        };
}

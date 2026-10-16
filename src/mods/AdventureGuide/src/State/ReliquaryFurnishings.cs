using AdventureGuide.Data;

namespace AdventureGuide.State;

/// <summary>
/// Which furniture set each room of the player's Reliquary holds, read from
/// the planning table. The game loads the table at login
/// (GameManager.LoadReliquary from CharSelectManager.Play), so a furnishing's
/// availability is known in every zone, not only in the Reliquary.
/// </summary>
public sealed class ReliquaryFurnishings : IFurnitureSlots
{
    private readonly Item?[] _items = new Item?[FurnishingPolicy.RoomSlots.Length];
    private readonly string?[] _keys = new string?[FurnishingPolicy.RoomSlots.Length];

    /// <summary>
    /// Re-read the room slots. Returns true when any slot holds a different
    /// item than at the last call. Reference checks only, so it runs every frame.
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
        return index >= 0 ? _keys[index] : null;
    }

    private static string? KeyOf(Item? item)
    {
        if (item == null || (GameData.PlayerInv != null && item == GameData.PlayerInv.Empty))
            return null;
        return "item:" + item.name.Trim().ToLowerInvariant();
    }

    // FurnishingPolicy.RoomSlots order.
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
            _ => null,
        };
}

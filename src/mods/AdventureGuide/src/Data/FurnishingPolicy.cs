namespace AdventureGuide.Data;

/// <summary>Whether a character's furnishings stand in the player's Reliquary.</summary>
public enum FurnishingStatus
{
    /// <summary>The character has spawns outside the planning table's rooms.</summary>
    Ungated,

    /// <summary>A room of the planning table holds the set that places it.</summary>
    Present,

    /// <summary>No room holds a set that places it, so it is nowhere in the world.</summary>
    Absent,
}

/// <summary>The items in the Reliquary planning table's room slots.</summary>
public interface IFurnitureSlots
{
    /// <summary>Stable key of the item in a room slot, or null when the slot is empty.</summary>
    string? ItemKeyIn(string slot);
}

/// <summary>
/// The planning table's build rule for furnishing characters. Building the
/// table turns on, in each room slot, the child that the slot's furniture set
/// names (PlanningTable.ExecuteBuild/CheckRoomAndBuild). Every room has the
/// same children, so a furnishing has one spawn per room, and it stands only
/// in the rooms whose slot holds its set.
/// </summary>
public static class FurnishingPolicy
{
    /// <summary>The room slots that ExecuteBuild builds, in PlanningTableUI's field order.</summary>
    public static readonly string[] RoomSlots = { "L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4" };

    public static bool IsRoomSlot(string slot) => Array.IndexOf(RoomSlots, slot) >= 0;

    /// <summary>A spawn without a set always exists; a furnishing while its room holds its set.</summary>
    public static bool IsPresent(SpawnPoint spawn, IFurnitureSlots slots) =>
        spawn.FurnitureSlot == null
        || string.Equals(
            slots.ItemKeyIn(spawn.FurnitureSlot),
            spawn.FurnitureItemStableKey,
            StringComparison.OrdinalIgnoreCase
        );

    /// <summary>
    /// Ungated when any spawn is not a furnishing; otherwise Present when a
    /// room holds the set of any of its spawns, else Absent.
    /// </summary>
    public static FurnishingStatus StatusOf(
        IReadOnlyList<SpawnPoint>? spawns,
        IFurnitureSlots slots
    )
    {
        if (spawns == null || spawns.Count == 0)
            return FurnishingStatus.Ungated;
        bool present = false;
        foreach (var spawn in spawns)
        {
            if (spawn.FurnitureSlot == null)
                return FurnishingStatus.Ungated;
            present |= IsPresent(spawn, slots);
        }
        return present ? FurnishingStatus.Present : FurnishingStatus.Absent;
    }

    /// <summary>"Requires Stone Vendor Set or Wood Vendor Set in a Reliquary room".</summary>
    public static string RequirementText(IEnumerable<string> setNames) =>
        "Requires "
        + string.Join(" or ", setNames.Distinct(StringComparer.OrdinalIgnoreCase))
        + " in a Reliquary room";
}

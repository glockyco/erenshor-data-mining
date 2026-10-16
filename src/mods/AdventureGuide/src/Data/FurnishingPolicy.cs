namespace AdventureGuide.Data;

/// <summary>The items in the Reliquary planning table's room slots.</summary>
public interface IFurnitureSlots
{
    /// <summary>Stable key of the item in a room slot, or null when the slot is empty.</summary>
    string? ItemKeyIn(string slot);
}

public static class FurnishingPolicy
{
    /// <summary>The room slots that ExecuteBuild builds, in PlanningTableUI's field order.</summary>
    public static readonly string[] RoomSlots = { "L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4" };

    public static bool IsRoomSlot(string slot) => Array.IndexOf(RoomSlots, slot) >= 0;
}

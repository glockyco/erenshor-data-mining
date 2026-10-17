namespace AdventureGuide.Data;

/// <summary>The items stored in the Reliquary planning table.</summary>
public interface IFurnitureSlots
{
    /// <summary>Stable key of the stored item in a planning slot, or null when empty.</summary>
    string? ItemKeyIn(string slot);
}

public static class FurnishingPolicy
{
    /// <summary>The room slots that ExecuteBuild builds, in PlanningTableUI's field order.</summary>
    public static readonly string[] RoomSlots = { "L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4" };
    public static readonly string[] PlanarSlots =
    {
        "PlanarFern",
        "PlanarBrax",
        "PlanarVith",
        "PlanarSol",
    };
    public static readonly string[] RuneSlots =
    {
        "Rune1",
        "Rune2",
        "Rune3",
        "Rune4",
        "Rune5",
        "Rune6",
    };

    public static bool IsRoomSlot(string slot) => Array.IndexOf(RoomSlots, slot) >= 0;

    public static bool IsPlanningSlot(string slot) =>
        Array.IndexOf(PlanarSlots, slot) >= 0 || Array.IndexOf(RuneSlots, slot) >= 0;
}

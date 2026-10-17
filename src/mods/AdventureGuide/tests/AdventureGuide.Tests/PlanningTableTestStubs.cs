// Minimal game objects for exercising the actual stored-slot mirror without Unity.
public sealed class Item
{
    public string name = "";

    public enum SlotType
    {
        General,
        Equipment,
    }

    public SlotType RequiredSlot;
}

public sealed class ItemIcon
{
    public Item? MyItem;
    public int Quantity;
}

public sealed class PlanningTableUI
{
    public ItemIcon L1 = new();
    public ItemIcon L2 = new();
    public ItemIcon L3 = new();
    public ItemIcon L4 = new();
    public ItemIcon R1 = new();
    public ItemIcon R2 = new();
    public ItemIcon R3 = new();
    public ItemIcon R4 = new();
    public ItemIcon PlanarFern = new();
    public ItemIcon PlanarBrax = new();
    public ItemIcon PlanarVith = new();
    public ItemIcon PlanarSol = new();
    public ItemIcon Rune1 = new();
    public ItemIcon Rune2 = new();
    public ItemIcon Rune3 = new();
    public ItemIcon Rune4 = new();
    public ItemIcon Rune5 = new();
    public ItemIcon Rune6 = new();
}

public sealed class PlanningInventory
{
    public Item Empty = new();
    public ItemIcon[] StoredSlots = [];
}

public static class GameData
{
    public static PlanningTableUI? PlanningUI;
    public static PlanningInventory? PlayerInv;
    public static bool AccountClaimedReliquary;
    public static string? ReliqDest;
    public static UnityEngine.Vector3 ReliqLanding;
    public static HashSet<string>? HasQuest;
    public static HashSet<string>? CompletedQuests;
    public static List<string>? Keyring;
    public static UnityEngine.Component? PlayerControl;
    public static UnityEngine.Component? GM;
    public static CharacterSlot? CurrentCharacterSlot;
    public static Stats? PlayerStats;
}

public sealed class CharacterSlot
{
    public int index;
    public string CharName = "";
}

public sealed class Character : UnityEngine.Component
{
    public bool Alive = true;
}

public sealed class NPC : UnityEngine.Component
{
    public string? StableKey;
}

public sealed class TreasureHunting : UnityEngine.Component
{
    public string TreasureZone = "";
    public UnityEngine.Vector3 TreasureLoc;
}

public sealed class Stats
{
    public int Level = 1;
}

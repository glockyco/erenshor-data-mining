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
    private readonly GuideData _data;
    private readonly Item?[] _items = new Item?[FurnishingPolicy.RoomSlots.Length];
    private readonly string?[] _keys = new string?[FurnishingPolicy.RoomSlots.Length];
    private readonly Dictionary<string, FurnishingStatus> _status = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly Dictionary<string, string> _requirements = new(
        StringComparer.OrdinalIgnoreCase
    );

    public ReliquaryFurnishings(GuideData data)
    {
        _data = data;
        IsAvailablePredicate = IsAvailable;
    }

    /// <summary>
    /// <see cref="IsAvailable"/> as a delegate created once: converting the
    /// method group at every call allocates.
    /// </summary>
    public Func<string, bool> IsAvailablePredicate { get; }

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
        if (changed)
        {
            _status.Clear();
            _requirements.Clear();
        }
        return changed;
    }

    public string? ItemKeyIn(string slot)
    {
        int index = Array.IndexOf(FurnishingPolicy.RoomSlots, slot);
        return index >= 0 ? _keys[index] : null;
    }

    /// <summary>Whether a spawn exists now: always for ordinary spawns, for furnishings per room.</summary>
    public bool IsPresent(Data.SpawnPoint spawn) => FurnishingPolicy.IsPresent(spawn, this);

    public FurnishingStatus StatusOf(string? characterKey)
    {
        if (characterKey == null)
            return FurnishingStatus.Ungated;
        if (_status.TryGetValue(characterKey, out var status))
            return status;
        _data.CharacterSpawns.TryGetValue(characterKey, out var spawns);
        status = FurnishingPolicy.StatusOf(spawns, this);
        _status[characterKey] = status;
        return status;
    }

    /// <summary>False only for a furnishing that no room holds.</summary>
    public bool IsAvailable(string characterKey) =>
        StatusOf(characterKey) != FurnishingStatus.Absent;

    /// <summary>The furniture sets to place for an absent furnishing; null otherwise.</summary>
    public string? RequirementText(string? characterKey)
    {
        if (characterKey == null || StatusOf(characterKey) != FurnishingStatus.Absent)
            return null;
        if (_requirements.TryGetValue(characterKey, out var text))
            return text;
        var names = new List<string>();
        foreach (var spawn in _data.CharacterSpawns[characterKey])
        {
            var key = spawn.FurnitureItemStableKey!;
            names.Add(_data.FurnitureSetNames.TryGetValue(key, out var name) ? name : key);
        }
        text = FurnishingPolicy.RequirementText(names);
        _requirements[characterKey] = text;
        return text;
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

#nullable enable

using SQLite;

// Prefab defaults only. Save-backed simulation state is deliberately absent.
[Table("AuthoredSims")]
public class AuthoredSimRecord
{
    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;
    public string PrefabGuid { get; set; } = string.Empty;
    public long PrefabLocalId { get; set; }
    public string PrefabPath { get; set; } = string.Empty;
    public string ObjectName { get; set; } = string.Empty;
    public string RawCharacterStableKey { get; set; } = string.Empty;
    public string NPCName { get; set; } = string.Empty;
    public string SeedClassName { get; set; } = string.Empty;
    public int SeedLevel { get; set; }
    public float SeedSkillLevel { get; set; }
    public bool SeedIsMale { get; set; }
    public string SeedHairName { get; set; } = string.Empty;
    public int SeedHairColor { get; set; }
    public int SeedSkinColor { get; set; }
    public bool IsGMCharacter { get; set; }
    public bool Rival { get; set; }
}

// Preserve repeated references and list order separately from prefab identity.
[Table("AuthoredSimReferences")]
public class AuthoredSimReferenceRecord
{
    [Indexed(Name = "AuthoredSimReferences_IDX", Order = 1, Unique = true)]
    public string SourceComponentKey { get; set; } = string.Empty;

    [Indexed(Name = "AuthoredSimReferences_IDX", Order = 2, Unique = true)]
    public int ReferenceIndex { get; set; }
    public string SourceScene { get; set; } = string.Empty;
    public string SourceScenePath { get; set; } = string.Empty;
    public string AuthoredSimStableKey { get; set; } = string.Empty;
}

// Position is the serialized EquippedItems list index, not an inferred slot.
[Table("AuthoredSimEquipment")]
public class AuthoredSimEquipmentRecord
{
    [Indexed(Name = "AuthoredSimEquipment_IDX", Order = 1, Unique = true)]
    public string AuthoredSimStableKey { get; set; } = string.Empty;

    [Indexed(Name = "AuthoredSimEquipment_IDX", Order = 2, Unique = true)]
    public int Position { get; set; }
    public string? ItemStableKey { get; set; }
}

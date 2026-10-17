#nullable enable

using SQLite;

/// <summary>Native UI slot contents and the serialized replenishment reference, if any.</summary>
[Table("UiItemSources")]
public class UiItemSourceRecord
{
    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;
    public string ComponentType { get; set; } = string.Empty;
    public string Scene { get; set; } = string.Empty;
    public string HierarchyPath { get; set; } = string.Empty;
    public string Slot { get; set; } = string.Empty;
    public string IconHierarchyPath { get; set; } = string.Empty;

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? SerializedItemStableKey { get; set; }
    public int SerializedQuantity { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ReplenishItemStableKey { get; set; }
    public string? ReplenishSourceKey { get; set; }
    public bool DisplayOnly { get; set; }
    public bool VendorSlot { get; set; }
    public bool LootSlot { get; set; }
    public bool BankSlot { get; set; }
    public bool MouseSlot { get; set; }
    public bool PlayerOwned { get; set; }
    public bool NotInInventory { get; set; }
    public string SlotType { get; set; } = string.Empty;
}

/// <summary>A placed object through which the player can open an acquisition UI.</summary>
[Table("UiItemAccessTargets")]
public class UiItemAccessTargetRecord
{
    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;
    public string Scene { get; set; } = string.Empty;
    public string HierarchyPath { get; set; } = string.Empty;
    public string Tag { get; set; } = string.Empty;
    public bool ActiveSelf { get; set; }
    public bool ActiveInHierarchy { get; set; }
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
}

/// <summary>One native QuestSpawnListener route that enables a UI access target.</summary>
[Table("UiItemAccessActivations")]
public class UiItemAccessActivationRecord
{
    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    [ForeignKey(typeof(UiItemAccessTargetRecord), "StableKey")]
    public string TargetStableKey { get; set; } = string.Empty;
    public string ActivatorStableKey { get; set; } = string.Empty;
    public string Scene { get; set; } = string.Empty;
    public string HierarchyPath { get; set; } = string.Empty;

    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? QuestStableKey { get; set; }

    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? AlternativeQuestStableKey { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
}

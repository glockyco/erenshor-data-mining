using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed class SourceCondition
{
    [JsonProperty("gate_key")]
    public string GateKey { get; set; } = "";

    [JsonProperty("gate_index")]
    public int GateIndex { get; set; }

    [JsonProperty("alternative_index")]
    public int AlternativeIndex { get; set; }

    [JsonProperty("atom_index")]
    public int AtomIndex { get; set; }

    [JsonProperty("predicate")]
    public string Predicate { get; set; } = "";

    [JsonProperty("reference_stable_key")]
    public string? ReferenceStableKey { get; set; }

    [JsonProperty("reference_slot")]
    public string? ReferenceSlot { get; set; }

    [JsonProperty("actor")]
    public string? Actor { get; set; }

    [JsonProperty("value")]
    public string? Value { get; set; }

    [JsonProperty("minimum")]
    public double? Minimum { get; set; }

    [JsonProperty("maximum")]
    public double? Maximum { get; set; }

    [JsonProperty("minimum_inclusive")]
    public bool MinimumInclusive { get; set; } = true;

    [JsonProperty("maximum_inclusive")]
    public bool MaximumInclusive { get; set; } = true;

    [JsonProperty("phase")]
    public string Phase { get; set; } = "";

    // Resolved at load, so current-state evaluation does not parse identities.
    [JsonIgnore]
    internal string? QuestDBName { get; set; }

    [JsonIgnore]
    internal string? GameId { get; set; }

    [JsonIgnore]
    internal GateAtom? GuidanceAtom { get; set; }
}

internal sealed class SourceGate
{
    public SourceCondition[][] Alternatives { get; }

    public SourceGate(SourceCondition[][] alternatives) => Alternatives = alternatives;
}

[JsonConverter(typeof(GuideRowConverter))]
public sealed class SourceLocation
{
    [JsonProperty("place_key")]
    public string PlaceKey { get; set; } = "";

    [JsonProperty("relation")]
    public string Relation { get; set; } = "";

    [JsonProperty("scene")]
    public string? Scene { get; set; }

    [JsonProperty("zone_stable_key")]
    public string? ZoneStableKey { get; set; }

    [JsonProperty("zone")]
    public string? Zone { get; set; }

    [JsonProperty("marker_stable_key")]
    public string? MarkerStableKey { get; set; }

    [JsonProperty("x")]
    public float? X { get; set; }

    [JsonProperty("y")]
    public float? Y { get; set; }

    [JsonProperty("z")]
    public float? Z { get; set; }

    [JsonProperty("player_level_min")]
    public int? PlayerLevelMin { get; set; }

    [JsonProperty("player_level_max")]
    public int? PlayerLevelMax { get; set; }

    [JsonProperty("conditions")]
    public List<SourceCondition> Conditions { get; set; } = new();

    [JsonProperty("entry_zone_line_keys")]
    public List<string> EntryZoneLineKeys { get; set; } = new();

    [JsonProperty("source_copy_stable_key")]
    public string? SourceCopyStableKey { get; set; }

    [JsonIgnore]
    internal SourceGate[] AvailabilityGates { get; set; } = Array.Empty<SourceGate>();

    [JsonIgnore]
    internal SpawnPoint? Spawn { get; set; }
}

public sealed class SourceFact : ItemSource
{
    [JsonProperty("kind")]
    public string Kind { get; set; } = "";

    [JsonProperty("place_set_key")]
    public string? PlaceSetKey { get; set; }

    [JsonProperty("conditions")]
    public List<SourceCondition> Conditions { get; set; } = new();

    [JsonIgnore]
    public IReadOnlyList<SourceLocation> Locations { get; internal set; } =
        Array.Empty<SourceLocation>();

    [JsonIgnore]
    internal SourceGate[] AvailabilityGates { get; set; } = Array.Empty<SourceGate>();
}

/// <summary>
/// The progression build's order of an acquisition's earliest way to its item.
/// Lower tiers come first, then lower depths, as first ways are chosen.
/// </summary>
public sealed class SourceRank
{
    [JsonProperty("tier"), JsonRequired]
    public int Tier { get; set; }

    [JsonProperty("depth"), JsonRequired]
    public int Depth { get; set; }
}

public sealed class ItemUseFact
{
    [JsonProperty("use_key")]
    public string UseKey { get; set; } = "";

    [JsonProperty("item_stable_key")]
    public string ItemStableKey { get; set; } = "";

    [JsonProperty("target_stable_key")]
    public string? TargetStableKey { get; set; }

    [JsonProperty("kind")]
    public string Kind { get; set; } = "";

    [JsonProperty("variant_key")]
    public string? VariantKey { get; set; }

    [JsonProperty("material_slot")]
    public int? MaterialSlot { get; set; }

    [JsonProperty("quantity_min")]
    public double? QuantityMin { get; set; }

    [JsonProperty("quantity_max")]
    public double? QuantityMax { get; set; }

    [JsonProperty("quantity_kind")]
    public string QuantityKind { get; set; } = "";

    [JsonProperty("outcome_key")]
    public string? OutcomeKey { get; set; }

    [JsonProperty("conditions")]
    public List<SourceCondition> Conditions { get; set; } = new();

    [JsonProperty("place_set_key")]
    public string? PlaceSetKey { get; set; }
}

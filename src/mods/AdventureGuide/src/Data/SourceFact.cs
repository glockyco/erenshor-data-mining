using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed class SourceCondition
{
    [JsonProperty("gate_key")]
    public string GateKey { get; set; } = "";

    [JsonProperty("group_index")]
    public int GroupIndex { get; set; }

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

    [JsonProperty("scope")]
    public string Scope { get; set; } = "";

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

public sealed class SourceLocation
{
    [JsonProperty("location_key")]
    public string LocationKey { get; set; } = "";

    [JsonProperty("relation")]
    public string Relation { get; set; } = "";

    [JsonProperty("scene")]
    public string? Scene { get; set; }

    [JsonProperty("zone_stable_key")]
    public string? ZoneStableKey { get; set; }

    [JsonProperty("placement_key")]
    public string? PlacementKey { get; set; }

    [JsonProperty("coordinate_stable_key")]
    public string? CoordinateStableKey { get; set; }

    [JsonProperty("x")]
    public float? X { get; set; }

    [JsonProperty("y")]
    public float? Y { get; set; }

    [JsonProperty("z")]
    public float? Z { get; set; }

    [JsonProperty("gate_scope")]
    public string? GateScope { get; set; }

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

public sealed class SourceFact
{
    [JsonProperty("acquisition_key")]
    public string AcquisitionKey { get; set; } = "";

    [JsonProperty("item_stable_key")]
    public string ItemStableKey { get; set; } = "";

    [JsonProperty("kind")]
    public string Kind { get; set; } = "";

    [JsonProperty("source_stable_key")]
    public string? SourceStableKey { get; set; }

    [JsonProperty("source_group_key")]
    public string? SourceGroupKey { get; set; }

    [JsonProperty("source_copy_stable_key")]
    public string? SourceCopyStableKey { get; set; }

    [JsonProperty("variant_key")]
    public string? VariantKey { get; set; }

    [JsonProperty("mechanic")]
    public string? Mechanic { get; set; }

    [JsonProperty("player_access_state")]
    public string PlayerAccessState { get; set; } = "";

    [JsonProperty("probability_kind")]
    public string ProbabilityKind { get; set; } = "";

    [JsonProperty("probability_min")]
    public double? ProbabilityMin { get; set; }

    [JsonProperty("probability_max")]
    public double? ProbabilityMax { get; set; }

    [JsonProperty("probability_basis")]
    public string? ProbabilityBasis { get; set; }

    [JsonProperty("probability_stage")]
    public string ProbabilityStage { get; set; } = "";

    [JsonProperty("quantity_min")]
    public double? QuantityMin { get; set; }

    [JsonProperty("quantity_max")]
    public double? QuantityMax { get; set; }

    [JsonProperty("quantity_kind")]
    public string QuantityKind { get; set; } = "";

    [JsonProperty("expected_quantity")]
    public double? ExpectedQuantity { get; set; }

    [JsonProperty("count_distribution")]
    public string? CountDistribution { get; set; }

    [JsonProperty("guarantee_scope")]
    public string? GuaranteeScope { get; set; }

    [JsonProperty("guaranteed_roll_count")]
    public int? GuaranteedRollCount { get; set; }

    [JsonProperty("conditions")]
    public List<SourceCondition> Conditions { get; set; } = new();

    [JsonProperty("locations")]
    public List<SourceLocation> Locations { get; set; } = new();

    [JsonIgnore]
    internal SourceGate[] AvailabilityGates { get; set; } = Array.Empty<SourceGate>();

    [JsonIgnore]
    internal Dictionary<string, SourceLocation> LocationsByKey { get; } =
        new(StringComparer.Ordinal);
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

    [JsonProperty("mechanic")]
    public string? Mechanic { get; set; }

    [JsonProperty("outcome_key")]
    public string? OutcomeKey { get; set; }

    [JsonProperty("conditions")]
    public List<SourceCondition> Conditions { get; set; } = new();

    [JsonProperty("locations")]
    public List<SourceLocation> Locations { get; set; } = new();
}

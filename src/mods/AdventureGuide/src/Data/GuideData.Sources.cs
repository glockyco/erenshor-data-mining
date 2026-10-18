using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed partial class GuideData
{
    public IReadOnlyDictionary<string, SourceFact> SourceFacts { get; private set; } =
        new Dictionary<string, SourceFact>(StringComparer.Ordinal);
    public IReadOnlyDictionary<string, ItemUseFact> ItemUses { get; private set; } =
        new Dictionary<string, ItemUseFact>(StringComparer.Ordinal);
    private IReadOnlyDictionary<string, string> _questStateKeys = new Dictionary<string, string>(
        StringComparer.Ordinal
    );

    private static void ValidateSourceFacts(GuideWrapper wrapper)
    {
        if (
            wrapper.SourceFacts == null
            || wrapper.ItemUses == null
            || wrapper.QuestStateKeys == null
        )
            throw new InvalidDataException(
                "Canonical source tables and quest-state keys are required"
            );
        foreach (var pair in wrapper.SourceFacts)
        {
            var fact = pair.Value;
            if (
                fact == null
                || string.IsNullOrWhiteSpace(pair.Key)
                || pair.Key != fact.AcquisitionKey
                || string.IsNullOrWhiteSpace(fact.ItemStableKey)
            )
                throw new InvalidDataException("Invalid canonical acquisition identity");
            if (
                fact.PlayerAccessState
                    is not (
                        "verified_player"
                        or "unconfirmed_player"
                        or "internal_only"
                        or "non_acquirable"
                    )
                || fact.ProbabilityStage is not ("native_pool" or "final_acquisition")
                || fact.ProbabilityKind
                    is not ("exact" or "bounded" or "unknown" or "not_applicable")
            )
                throw new InvalidDataException($"Invalid canonical source semantics: {pair.Key}");
            if (fact.PlayerAccessState == "verified_player" && !SupportedAcquisitionKind(fact.Kind))
                throw new InvalidDataException(
                    $"unsupported canonical acquisition kind: {fact.Kind}"
                );
            ValidateRange(fact.ProbabilityMin, fact.ProbabilityMax, 100, pair.Key);
            ValidateRange(fact.QuantityMin, fact.QuantityMax, null, pair.Key);
            if (fact.ExpectedQuantity is double expected && (!Finite(expected) || expected < 0))
                throw new InvalidDataException($"Invalid canonical expected quantity: {pair.Key}");
            if (fact.Conditions == null || fact.Locations == null)
                throw new InvalidDataException(
                    $"Canonical source children are required: {pair.Key}"
                );
        }
        foreach (var pair in wrapper.ItemUses)
        {
            var use = pair.Value;
            if (
                use == null
                || pair.Key != use.UseKey
                || string.IsNullOrWhiteSpace(use.ItemStableKey)
                || use.Conditions == null
                || use.Locations == null
                || use.MaterialSlot < 0
            )
                throw new InvalidDataException("Invalid canonical item-use identity");
            ValidateRange(use.QuantityMin, use.QuantityMax, null, pair.Key);
        }
        foreach (var pair in wrapper.QuestStateKeys)
            if (string.IsNullOrWhiteSpace(pair.Key) || string.IsNullOrWhiteSpace(pair.Value))
                throw new InvalidDataException("Invalid canonical quest-state key");
        ValidateNativeRequirements(wrapper);
    }

    private static void ValidateNativeRequirements(GuideWrapper wrapper)
    {
        foreach (var quest in wrapper.Quests!)
        {
            var expected = new HashSet<string>(StringComparer.Ordinal);
            foreach (var use in wrapper.ItemUses!.Values)
                if (use.Kind == "quest_requirement" && use.TargetStableKey == quest.StableKey)
                    expected.Add(use.UseKey);
            var referenced = new HashSet<string>(StringComparer.Ordinal);
            var identities = new HashSet<(string, string?, string?)>();
            if (quest.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                {
                    if (item.UseKeys == null)
                    {
                        if (
                            item.VariantKey != null
                            || expected.Any(key =>
                                wrapper.ItemUses[key].ItemStableKey == item.ItemStableKey
                            )
                        )
                            throw new InvalidDataException(
                                $"Native requirement is missing slot evidence: {quest.StableKey}"
                            );
                        continue;
                    }
                    if (
                        quest.IsGuideOnly
                        || item.UseKeys.Count == 0
                        || item.OrGroup != null
                        || item.Quantity < 0
                        || item.VariantKey is ""
                        || !identities.Add(
                            (item.ItemStableKey, item.VariantKey, item.OutputQuality)
                        )
                    )
                        throw new InvalidDataException("Invalid native requirement identity");
                    double quantity = 0;
                    foreach (string key in item.UseKeys)
                    {
                        if (
                            string.IsNullOrWhiteSpace(key)
                            || !wrapper.ItemUses.TryGetValue(key, out var use)
                            || use.Kind != "quest_requirement"
                            || use.TargetStableKey != quest.StableKey
                            || use.ItemStableKey != item.ItemStableKey
                            || use.VariantKey != item.VariantKey
                            || !referenced.Add(key)
                            || use.QuantityKind != "exact"
                            || use.QuantityMin is not double minimum
                            || use.QuantityMax != minimum
                            || minimum < 0
                            || minimum != Math.Truncate(minimum)
                            || RequestedQuality(use) != item.OutputQuality
                        )
                            throw new InvalidDataException(
                                $"Mismatched native requirement slot: {key}"
                            );
                        quantity += minimum;
                    }
                    if (quantity != item.Quantity)
                        throw new InvalidDataException(
                            "Native requirement quantity differs from slots"
                        );
                }
            if (!expected.SetEquals(referenced))
                throw new InvalidDataException(
                    $"Native requirement slots are not fully represented: {quest.StableKey}"
                );
            ValidateNativeCollectSteps(quest);
        }
    }

    private static string? RequestedQuality(ItemUseFact use)
    {
        string? quality = null;
        foreach (var condition in use.Conditions)
            if (
                condition.Predicate == "quality"
                && condition.Phase is "availability" or "operation_input"
            )
            {
                if (condition.Value == null || (quality != null && quality != condition.Value))
                    throw new InvalidDataException("Invalid native requirement quality");
                quality = condition.Value;
            }
        return quality;
    }

    private static void ValidateNativeCollectSteps(QuestEntry quest)
    {
        var requirements = quest.RequiredItems;
        var matched = new HashSet<RequiredItemInfo>();
        var closedVariants = new HashSet<string>(StringComparer.Ordinal);
        string? previousVariant = null;
        bool variantsEnded = false;
        if (quest.Steps != null)
            foreach (var step in quest.Steps)
            {
                if (step.RequirementVariant != previousVariant)
                {
                    if (previousVariant != null)
                    {
                        closedVariants.Add(previousVariant);
                        variantsEnded |= step.RequirementVariant == null;
                    }
                    if (
                        step.RequirementVariant != null
                        && (variantsEnded || closedVariants.Contains(step.RequirementVariant))
                    )
                        throw new InvalidDataException("Native variant bundles must be contiguous");
                    previousVariant = step.RequirementVariant;
                }
                if (step.RequirementVariant != null && step.Action != "collect")
                    throw new InvalidDataException("Native variants require collect steps");
                if (step.Action != "collect")
                    continue;
                RequiredItemInfo? item = null;
                if (requirements != null)
                    foreach (var candidate in requirements)
                        if (
                            candidate.UseKeys != null
                            && candidate.ItemStableKey == step.TargetKey
                            && candidate.VariantKey == step.RequirementVariant
                            && candidate.OutputQuality == step.OutputQuality
                        )
                        {
                            item = candidate;
                            break;
                        }
                if (item == null)
                {
                    if (
                        step.RequirementVariant != null
                        || requirements?.Any(candidate =>
                            candidate.UseKeys != null && candidate.ItemStableKey == step.TargetKey
                        ) == true
                    )
                        throw new InvalidDataException("Unbound native collect step");
                    continue;
                }
                if (step.OrGroup != null || step.Quantity != item.Quantity || !matched.Add(item))
                    throw new InvalidDataException("Invalid native collect requirement");
            }
        if (requirements != null)
            foreach (var item in requirements)
                if (item.UseKeys != null && !matched.Contains(item))
                    throw new InvalidDataException("Native requirement has no collect step");
    }

    private void LoadSourceFacts(GuideWrapper wrapper)
    {
        SourceFacts = wrapper.SourceFacts!;
        ItemUses = wrapper.ItemUses!;
        _questStateKeys = wrapper.QuestStateKeys!;
        var lines = new Dictionary<string, int>(StringComparer.Ordinal);
        for (int index = 0; index < ZoneLines.Count; index++)
            if (!string.IsNullOrEmpty(ZoneLines[index].StableKey))
                lines.Add(ZoneLines[index].StableKey, index);
        var placements = new Dictionary<string, SpawnPoint>(StringComparer.Ordinal);
        foreach (var spawns in CharacterSpawns.Values)
        foreach (var spawn in spawns)
            if (!string.IsNullOrEmpty(spawn.StableKey))
                placements.TryAdd(spawn.StableKey, spawn);
        foreach (var fact in SourceFacts.Values)
        {
            fact.AvailabilityGates = CompileSourceConditions(fact.Conditions);
            foreach (var location in fact.Locations)
            {
                ValidateLocation(location);
                if (!fact.LocationsByKey.TryAdd(location.LocationKey, location))
                    throw new InvalidDataException(
                        $"Duplicate canonical source location: {location.LocationKey}"
                    );
                location.AvailabilityGates = CompileSourceConditions(location.Conditions);
                if (
                    location.Scene != null
                    && location.X.HasValue
                    && location.Y.HasValue
                    && location.Z.HasValue
                    && location.Relation is "fixed" or "spawn" or "interaction"
                )
                {
                    var entries = location.EntryZoneLineKeys.Count == 0 ? null : new List<int>();
                    foreach (string entry in location.EntryZoneLineKeys)
                    {
                        if (!lines.TryGetValue(entry, out int index))
                            throw new InvalidDataException(
                                $"Missing canonical source entrance: {entry}"
                            );
                        entries!.Add(index);
                    }
                    SpawnPoint? original = null;
                    string? coordinateKey = location.CoordinateStableKey ?? location.PlacementKey;
                    if (coordinateKey != null)
                        placements.TryGetValue(coordinateKey, out original);
                    location.Spawn = new SpawnPoint
                    {
                        StableKey =
                            original?.StableKey ?? location.PlacementKey ?? location.LocationKey,
                        Scene = location.Scene,
                        X = location.X.Value,
                        Y = location.Y.Value,
                        Z = location.Z.Value,
                        Entries = entries,
                        Condition = original?.Condition,
                        IsDirectlyPlaced = original?.IsDirectlyPlaced ?? false,
                        SourceScript = original?.SourceScript,
                    };
                }
            }
        }
        foreach (var use in ItemUses.Values)
        {
            CompileSourceConditions(use.Conditions);
            foreach (var location in use.Locations)
            {
                ValidateLocation(location);
                CompileSourceConditions(location.Conditions);
            }
        }
        foreach (var quest in All)
        {
            if (quest.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                    BindSourceFacts(item.Sources);
            if (quest.Steps != null)
                foreach (var step in quest.Steps)
                    BindSourceFacts(step.Sources);
        }
        foreach (var item in GateItems.Values)
            BindSourceFacts(item.Sources);
    }

    private void BindSourceFacts(List<ItemSource>? sources)
    {
        if (sources == null)
            return;
        foreach (var source in sources)
        {
            if (source.AcquisitionKey != null)
            {
                if (
                    !SourceFacts.TryGetValue(source.AcquisitionKey, out var fact)
                    || fact.PlayerAccessState != "verified_player"
                    || fact.ProbabilityStage != "final_acquisition"
                    || fact.ProbabilityMax is <= 0
                )
                    throw new InvalidDataException(
                        $"Missing or non-actionable source acquisition: {source.AcquisitionKey}"
                    );
                source.CanonicalFact = fact;
                if (source.LocationKey != null)
                {
                    if (!fact.LocationsByKey.TryGetValue(source.LocationKey, out var location))
                        throw new InvalidDataException(
                            $"Missing canonical source location: {source.LocationKey}"
                        );
                    source.CanonicalLocation = location;
                }
                else if (source.X.HasValue || source.Y.HasValue || source.Z.HasValue)
                    throw new InvalidDataException(
                        "Positioned canonical source requires a location identity"
                    );
                source.CanonicalSourceId = source.AcquisitionKey + "|" + (source.LocationKey ?? "");
            }
            else if (source.LocationKey != null)
                throw new InvalidDataException("Source location requires an acquisition identity");
            if (source.UseKey != null)
            {
                if (!ItemUses.TryGetValue(source.UseKey, out var use))
                    throw new InvalidDataException($"Missing canonical item use: {source.UseKey}");
                source.CanonicalUse = use;
                source.CanonicalSourceId ??= source.UseKey;
            }
            if (source.OperationUseKeys != null)
                foreach (string key in source.OperationUseKeys)
                    if (
                        source.AcquisitionKey == null
                        || !ItemUses.TryGetValue(key, out var input)
                        || input.OutcomeKey != source.AcquisitionKey
                    )
                        throw new InvalidDataException($"Unbound canonical operation input: {key}");
            BindSourceFacts(source.Children);
        }
    }

    private SourceGate[] CompileSourceConditions(List<SourceCondition> conditions)
    {
        var identities = new HashSet<(string, string, string, int, int)>();
        var gates =
            new Dictionary<(string, string), SortedDictionary<int, List<SourceCondition>>>();
        foreach (var atom in conditions)
        {
            ValidateSourceCondition(atom);
            if (
                !identities.Add(
                    (atom.Scope, atom.GateKey, atom.Phase, atom.GroupIndex, atom.AtomIndex)
                )
            )
                throw new InvalidDataException("Duplicate canonical source condition");
            if (atom.Phase != "availability")
                continue;
            if (atom.Predicate is "quest_done" or "quest_not_done")
            {
                if (!_questStateKeys.TryGetValue(atom.ReferenceStableKey!, out var dbName))
                    throw new InvalidDataException(
                        $"Missing canonical quest-state reference: {atom.ReferenceStableKey}"
                    );
                atom.QuestDBName = dbName;
            }
            else if (atom.Predicate == "key_held")
            {
                if (
                    !GateItems.TryGetValue(atom.ReferenceStableKey!, out var item)
                    || string.IsNullOrWhiteSpace(item.GameId)
                )
                    throw new InvalidDataException(
                        $"Missing canonical key metadata: {atom.ReferenceStableKey}"
                    );
                atom.GameId = item.GameId;
            }
            atom.GuidanceAtom = SourceGuidanceAtom(atom);
            var identity = (atom.Scope, atom.GateKey);
            if (!gates.TryGetValue(identity, out var groups))
                gates.Add(identity, groups = new());
            if (!groups.TryGetValue(atom.GroupIndex, out var group))
                groups.Add(atom.GroupIndex, group = new());
            group.Add(atom);
        }
        var result = new SourceGate[gates.Count];
        int index = 0;
        foreach (var groups in gates.Values)
        {
            var alternatives = new SourceCondition[groups.Count][];
            int groupIndex = 0;
            foreach (var group in groups.Values)
                alternatives[groupIndex++] = group.ToArray();
            result[index++] = new SourceGate(alternatives);
        }
        return result;
    }

    private GateAtom? SourceGuidanceAtom(SourceCondition atom)
    {
        GateAtomKind? kind = atom.Predicate switch
        {
            "quest_done" => GateAtomKind.QuestDone,
            "quest_not_done" => GateAtomKind.QuestNotDone,
            "item_held" => GateAtomKind.ItemHeld,
            "key_held" => GateAtomKind.KeyHeld,
            "room_furnished" => GateAtomKind.RoomFurnished,
            "account_state" => GateAtomKind.AccountState,
            "encounter_won" => GateAtomKind.EncounterWon,
            _ => null,
        };
        if (atom.Predicate == "planning_slot_item")
        {
            foreach (var groups in Conditions)
            foreach (var group in groups)
            foreach (var candidate in group)
                if (
                    candidate.Kind == GateAtomKind.PlanningSlotItem
                    && candidate.Ref == atom.ReferenceStableKey
                    && candidate.Slot == atom.ReferenceSlot
                )
                    return candidate;
            throw new InvalidDataException(
                "Canonical planning condition requires a generated planning instruction"
            );
        }
        return kind.HasValue
            ? new GateAtom
            {
                Kind = kind.Value,
                Ref = atom.QuestDBName ?? atom.ReferenceStableKey!,
                Slot = atom.ReferenceSlot,
                Actor = atom.Actor,
                Value = atom.Value,
                Phase = atom.Phase,
                Scope = atom.Scope,
                GameId = atom.GameId,
            }
            : null;
    }

    private static void ValidateSourceCondition(SourceCondition atom)
    {
        if (
            atom == null
            || string.IsNullOrWhiteSpace(atom.GateKey)
            || string.IsNullOrWhiteSpace(atom.Scope)
            || atom.GroupIndex < 0
            || atom.AtomIndex < 0
        )
            throw new InvalidDataException("Invalid canonical source condition identity");
        if (
            atom.Phase
            is not (
                "availability"
                or "source_initialization"
                or "operation_input"
                or "operation_outcome"
                or "mechanic_parameter"
            )
        )
            throw new InvalidDataException($"Unknown canonical source phase: {atom.Phase}");
        if (atom.Actor is not (null or "player" or "sim" or "sim_player" or "enemy" or "account"))
            throw new InvalidDataException($"Unknown canonical source actor: {atom.Actor}");
        if (
            atom.Predicate
            is not (
                "never"
                or "quest_done"
                or "quest_not_done"
                or "room_furnished"
                or "planning_slot_item"
                or "key_held"
                or "item_held"
                or "item_not_owned"
                or "encounter_won"
                or "actor_level"
                or "actor_class"
                or "account_state"
                or "time_of_day"
                or "zone_use"
                or "quality"
                or "formula_operand"
                or "route"
                or "source_replenishment"
            )
        )
            throw new InvalidDataException($"Unknown canonical source predicate: {atom.Predicate}");
        if (
            atom.Predicate
            is "quest_done"
                or "quest_not_done"
                or "room_furnished"
                or "planning_slot_item"
                or "key_held"
                or "item_held"
                or "item_not_owned"
                or "encounter_won"
                or "actor_class"
                or "zone_use"
        )
            if (string.IsNullOrWhiteSpace(atom.ReferenceStableKey))
                throw new InvalidDataException(
                    $"Missing canonical source reference: {atom.Predicate}"
                );
        if (
            atom.Predicate == "account_state"
            && (
                atom.ReferenceStableKey != EncounterStateKeys.ReliquaryClaimed
                || atom.Actor != "account"
                || atom.Value is not ("true" or "false")
                || atom.Phase is not ("availability" or "operation_outcome")
            )
        )
            throw new InvalidDataException("Invalid canonical account condition");
        if (atom.Predicate is "room_furnished" or "planning_slot_item")
            if (
                atom.ReferenceSlot == null
                || (
                    atom.Predicate == "room_furnished"
                        ? !FurnishingPolicy.IsRoomSlot(atom.ReferenceSlot)
                        : !FurnishingPolicy.IsPlanningSlot(atom.ReferenceSlot)
                )
            )
                throw new InvalidDataException("Invalid canonical stored-item slot");
        if (
            atom.Predicate == "actor_level"
            && (atom.Actor == null || atom.Minimum == null && atom.Maximum == null)
        )
            throw new InvalidDataException(
                "Canonical actor-level condition requires an actor and a bound"
            );
        if (atom.Predicate == "time_of_day" && atom.Value is not ("day" or "night"))
            throw new InvalidDataException("Invalid canonical time window");
        ValidateRange(atom.Minimum, atom.Maximum, null, atom.GateKey);
    }

    private static void ValidateLocation(SourceLocation location)
    {
        if (
            location == null
            || string.IsNullOrWhiteSpace(location.LocationKey)
            || location.Conditions == null
            || location.EntryZoneLineKeys == null
            || location.Relation
                is not (
                    "fixed"
                    or "spawn"
                    or "interaction"
                    or "mechanic_zone"
                    or "possible_treasure"
                    or "unlocated"
                )
        )
            throw new InvalidDataException("Invalid canonical source location");
        bool any = location.X.HasValue || location.Y.HasValue || location.Z.HasValue;
        if (
            any
            && (
                !location.X.HasValue
                || !location.Y.HasValue
                || !location.Z.HasValue
                || !Finite(location.X.Value)
                || !Finite(location.Y.Value)
                || !Finite(location.Z.Value)
            )
        )
            throw new InvalidDataException(
                "Canonical source location requires complete finite coordinates"
            );
        if (location.Relation == "unlocated" && any)
            throw new InvalidDataException("Unlocated canonical source cannot invent coordinates");
        foreach (var atom in location.Conditions)
            if (atom.Predicate == "account_state" && atom.Scope != location.LocationKey)
                throw new InvalidDataException(
                    "Canonical account condition must retain its actual location scope"
                );
    }

    private static bool SupportedAcquisitionKind(string kind) =>
        kind
            is "character_drop"
                or "vendor"
                or "dialog"
                or "crafting"
                or "quest_reward"
                or "mining"
                or "fishing"
                or "item_bag"
                or "item_drop"
                or "spell_created"
                or "item_conversion"
                or "common_world_item"
                or "special_world_drop"
                or "fishing_bonus"
                or "starting_class"
                or "auction_house"
                or "ui_grant";

    private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);

    private static void ValidateRange(
        double? minimum,
        double? maximum,
        double? ceiling,
        string identity
    )
    {
        if (
            minimum is double low
                && (!Finite(low) || low < 0 || ceiling.HasValue && low > ceiling.Value)
            || maximum is double high
                && (!Finite(high) || high < 0 || ceiling.HasValue && high > ceiling.Value)
            || minimum.HasValue && maximum.HasValue && minimum.Value > maximum.Value
        )
            throw new InvalidDataException($"Invalid canonical numeric range: {identity}");
    }
}

internal sealed partial class GuideWrapper
{
    [JsonProperty("_source_facts"), JsonRequired]
    public Dictionary<string, SourceFact> SourceFacts { get; set; } = new(StringComparer.Ordinal);

    [JsonProperty("_item_uses"), JsonRequired]
    public Dictionary<string, ItemUseFact> ItemUses { get; set; } = new(StringComparer.Ordinal);

    [JsonProperty("_quest_state_keys"), JsonRequired]
    public Dictionary<string, string> QuestStateKeys { get; set; } = new(StringComparer.Ordinal);
}

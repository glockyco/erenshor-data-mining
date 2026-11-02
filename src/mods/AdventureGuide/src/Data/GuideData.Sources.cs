using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed partial class GuideData
{
    public IReadOnlyDictionary<string, SourceFact> Sources { get; private set; } =
        new Dictionary<string, SourceFact>(StringComparer.Ordinal);
    public IReadOnlyDictionary<string, List<SourceLocation>> PlaceSets { get; private set; } =
        new Dictionary<string, List<SourceLocation>>(StringComparer.Ordinal);
    public IReadOnlyDictionary<string, ItemUseFact> ItemUses { get; private set; } =
        new Dictionary<string, ItemUseFact>(StringComparer.Ordinal);
    private IReadOnlyDictionary<string, string> _questStateKeys = new Dictionary<string, string>(
        StringComparer.Ordinal
    );

    private static void ValidatePublicSources(GuideWrapper wrapper)
    {
        if (
            wrapper.Sources == null
            || wrapper.PlaceSets == null
            || wrapper.ItemUses == null
            || wrapper.QuestStateKeys == null
        )
            throw new InvalidDataException(
                "Public sources, places, uses and quest-state keys are required"
            );
        foreach (var pair in wrapper.Sources)
        {
            var source = pair.Value;
            if (
                source == null
                || string.IsNullOrWhiteSpace(pair.Key)
                || string.IsNullOrWhiteSpace(source.ItemStableKey)
                || string.IsNullOrWhiteSpace(source.Kind)
                || source.Conditions == null
                || source.PlaceSetKey != null && !wrapper.PlaceSets.ContainsKey(source.PlaceSetKey)
            )
                throw new InvalidDataException($"Invalid public source: {pair.Key}");
            if (source.Rank is { } rank && (rank.Tier < 0 || rank.Depth < 0))
                throw new InvalidDataException($"Invalid source rank: {pair.Key}");
            ValidateSources(new List<ItemSource> { source }, source.Name ?? "", pair.Key);
        }
        foreach (var pair in wrapper.ItemUses)
        {
            var use = pair.Value;
            if (
                use == null
                || pair.Key != use.UseKey
                || string.IsNullOrWhiteSpace(use.ItemStableKey)
                || use.Conditions == null
                || use.PlaceSetKey != null && !wrapper.PlaceSets.ContainsKey(use.PlaceSetKey)
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
                        item.UseKeys.Count == 0
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
            if (condition.Predicate == "quality")
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

    private void LoadPublicSources(GuideWrapper wrapper)
    {
        Sources = wrapper.Sources;
        PlaceSets = wrapper.PlaceSets;
        ItemUses = wrapper.ItemUses;
        _questStateKeys = wrapper.QuestStateKeys;
        var lines = new Dictionary<string, int>(StringComparer.Ordinal);
        for (int index = 0; index < ZoneLines.Count; index++)
            if (!string.IsNullOrEmpty(ZoneLines[index].StableKey))
                lines.Add(ZoneLines[index].StableKey, index);
        var placements = new Dictionary<string, SpawnPoint>(StringComparer.Ordinal);
        foreach (var spawns in CharacterSpawns.Values)
        foreach (var spawn in spawns)
        {
            if (string.IsNullOrEmpty(spawn.StableKey))
                continue;
            if (placements.TryGetValue(spawn.StableKey, out var previous))
            {
                if (
                    !string.Equals(previous.Scene, spawn.Scene, StringComparison.OrdinalIgnoreCase)
                    || previous.X != spawn.X
                    || previous.Y != spawn.Y
                    || previous.Z != spawn.Z
                )
                    throw new InvalidDataException($"Conflicting spawn marker: {spawn.StableKey}");
            }
            else
                placements.Add(spawn.StableKey, spawn);
        }
        foreach (var places in PlaceSets.Values)
        {
            var identities = new HashSet<string>(StringComparer.Ordinal);
            foreach (var location in places)
            {
                if (location == null)
                    throw new InvalidDataException("Invalid canonical source location");
                SpawnPoint? original = null;
                if (location.MarkerStableKey != null)
                {
                    if (placements.TryGetValue(location.MarkerStableKey, out original))
                        RestoreMarkerLocation(location, original);
                    else if (
                        location.Scene == null
                        || !location.X.HasValue
                        || !location.Y.HasValue
                        || !location.Z.HasValue
                    )
                        throw new InvalidDataException(
                            $"Missing public place marker: {location.MarkerStableKey}"
                        );
                }
                ValidateLocation(location);
                if (!identities.Add(location.PlaceKey))
                    throw new InvalidDataException($"Duplicate public place: {location.PlaceKey}");
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
                                $"Missing public place entrance: {entry}"
                            );
                        entries!.Add(index);
                    }
                    location.Spawn = new SpawnPoint
                    {
                        StableKey =
                            original?.StableKey ?? location.MarkerStableKey ?? location.PlaceKey,
                        Scene = location.Scene,
                        X = location.X.Value,
                        Y = location.Y.Value,
                        Z = location.Z.Value,
                        Entries = entries,
                        Condition = original?.Condition,
                        IsDirectlyPlaced = original?.IsDirectlyPlaced ?? false,
                        SourceScript = original?.SourceScript,
                        Activations = original?.Activations,
                    };
                }
            }
        }
        foreach (var source in Sources.Values)
        {
            source.AvailabilityGates = CompileSourceConditions(source.Conditions);
            source.Locations =
                source.PlaceSetKey == null
                    ? Array.Empty<SourceLocation>()
                    : PlaceSets[source.PlaceSetKey];
        }
        foreach (var use in ItemUses.Values)
            CompileSourceConditions(use.Conditions);
        var resolvedLists = new HashSet<List<ItemSource>>();
        foreach (var quest in All)
        {
            if (quest.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                    ResolveSources(item.Sources, resolvedLists);
            if (quest.Steps != null)
                foreach (var step in quest.Steps)
                    ResolveSources(step.Sources, resolvedLists);
        }
        foreach (var item in GateItems.Values)
            ResolveSources(item.Sources, resolvedLists);
    }

    private void RestoreMarkerLocation(SourceLocation location, SpawnPoint spawn)
    {
        if (
            location.Scene != null
                && !string.Equals(location.Scene, spawn.Scene, StringComparison.OrdinalIgnoreCase)
            || location.X.HasValue && location.X != spawn.X
            || location.Y.HasValue && location.Y != spawn.Y
            || location.Z.HasValue && location.Z != spawn.Z
        )
            throw new InvalidDataException($"Conflicting public place marker: {spawn.StableKey}");
        location.Scene ??= spawn.Scene;
        location.X ??= spawn.X;
        location.Y ??= spawn.Y;
        location.Z ??= spawn.Z;
        if (!ZoneLookup.TryGetValue(spawn.Scene, out var zone))
        {
            if (location.Zone == null || location.ZoneStableKey == null)
                throw new InvalidDataException($"Missing public place zone for {spawn.StableKey}");
            return;
        }
        if (
            location.Zone != null && location.Zone != zone.DisplayName
            || location.ZoneStableKey != null && location.ZoneStableKey != zone.StableKey
        )
            throw new InvalidDataException($"Conflicting public place zone for {spawn.StableKey}");
        location.Zone ??= zone.DisplayName;
        location.ZoneStableKey ??= zone.StableKey;
    }

    private void ResolveSources(List<ItemSource>? sources, HashSet<List<ItemSource>> resolvedLists)
    {
        if (sources == null || !resolvedLists.Add(sources))
            return;
        for (int index = 0; index < sources.Count; index++)
        {
            var source = sources[index];
            // Shared objects can occur in different lists. Expand every list once
            // so each path retains every place of its sources.
            ResolveSources(source.Children, resolvedLists);
            if (source.UseKey != null)
            {
                if (!ItemUses.TryGetValue(source.UseKey, out var use))
                    throw new InvalidDataException($"Missing public item use: {source.UseKey}");
                source.CanonicalUse = use;
                source.CanonicalSourceId = source.UseKey;
            }
            if (source.AcquisitionKey == null)
                continue;
            if (!Sources.TryGetValue(source.AcquisitionKey, out var fact))
                throw new InvalidDataException($"Missing public source: {source.AcquisitionKey}");
            source.ApplyPresentation(fact);
            source.CanonicalFact = fact;
            source.Rank = fact.Rank;
            var template = source.Copy();
            int count = Math.Max(1, fact.Locations.Count);
            for (int place = 0; place < count; place++)
            {
                var resolved = place == 0 ? source : template.Copy();
                var location = fact.Locations.Count == 0 ? null : fact.Locations[place];
                resolved.CanonicalLocation = location;
                resolved.LocationKey = location?.PlaceKey;
                resolved.Scene = location?.Scene;
                resolved.Zone = location?.Zone;
                resolved.X = location?.X;
                resolved.Y = location?.Y;
                resolved.Z = location?.Z;
                resolved.EntryZoneLineKeys = location?.EntryZoneLineKeys;
                resolved.CanonicalSourceId =
                    source.AcquisitionKey + "|" + (location?.PlaceKey ?? "");
                if (location?.Relation == "possible_treasure")
                {
                    resolved.Type = "treasure_chest";
                    resolved.Name = "Treasure map chest";
                    resolved.Instruction = "Read a Treasure Map and dig at the marked spot.";
                    resolved.Level = location.PlayerLevelMin;
                    resolved.LevelMax = location.PlayerLevelMax;
                }
                if (place > 0)
                    sources.Insert(++index, resolved);
            }
        }
    }

    private SourceGate[] CompileSourceConditions(List<SourceCondition> conditions)
    {
        var identities = new HashSet<(int, int, int)>();
        var gates = new SortedDictionary<int, SortedDictionary<int, List<SourceCondition>>>();
        foreach (var atom in conditions)
        {
            ValidateSourceCondition(atom);
            if (!identities.Add((atom.GateIndex, atom.AlternativeIndex, atom.AtomIndex)))
                throw new InvalidDataException("Duplicate canonical source condition");
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
            if (!gates.TryGetValue(atom.GateIndex, out var groups))
                gates.Add(atom.GateIndex, groups = new());
            if (!groups.TryGetValue(atom.AlternativeIndex, out var group))
                groups.Add(atom.AlternativeIndex, group = new());
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
                Quantity =
                    atom.Predicate == "encounter_won" && atom.Minimum.HasValue
                        ? checked((int)atom.Minimum.Value)
                        : 1,
                Slot = atom.ReferenceSlot,
                Actor = atom.Actor,
                Value = atom.Value,
                Phase = atom.Phase,
                GameId = atom.GameId,
            }
            : null;
    }

    private static void ValidateSourceCondition(SourceCondition atom)
    {
        if (
            atom == null
            || string.IsNullOrWhiteSpace(atom.GateKey)
            || atom.GateIndex < 0
            || atom.AlternativeIndex < 0
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
        if (
            atom.Predicate == "encounter_won"
            && atom.Minimum.HasValue
            && (
                atom.Minimum.Value < 1
                || atom.Minimum.Value > int.MaxValue
                || Math.Truncate(atom.Minimum.Value) != atom.Minimum.Value
            )
        )
            throw new InvalidDataException("Invalid canonical encounter defeat quantity");
    }

    private static void ValidateLocation(SourceLocation location)
    {
        if (
            location == null
            || string.IsNullOrWhiteSpace(location.PlaceKey)
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
    }

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
    [JsonProperty("_sources"), JsonRequired]
    public Dictionary<string, SourceFact> Sources { get; set; } = new(StringComparer.Ordinal);

    [JsonProperty("_place_sets"), JsonRequired]
    public Dictionary<string, List<SourceLocation>> PlaceSets { get; set; } =
        new(StringComparer.Ordinal);

    [JsonProperty("_item_uses"), JsonRequired]
    public Dictionary<string, ItemUseFact> ItemUses { get; set; } = new(StringComparer.Ordinal);

    [JsonProperty("_quest_state_keys"), JsonRequired]
    public Dictionary<string, string> QuestStateKeys { get; set; } = new(StringComparer.Ordinal);
}

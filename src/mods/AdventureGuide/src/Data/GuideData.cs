using System.Reflection;
using AdventureGuide.Config;
using Newtonsoft.Json;

namespace AdventureGuide.Data;

/// <summary>
/// Loads and holds the quest guide database from the embedded JSON resource.
/// The JSON has a wrapper structure with lookup tables and a quests array.
/// </summary>
public sealed partial class GuideData
{
    private readonly Dictionary<string, QuestEntry> _byDBName = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly Dictionary<string, QuestEntry> _byStableKey = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly List<QuestEntry> _all = new();
    private readonly Dictionary<string, string> _displayToScene = new(
        StringComparer.OrdinalIgnoreCase
    );

    // Game quests the guide leaves out on purpose (unobtainable placeholders
    // and quests nothing in the game can finish); never shown as stubs.
    private readonly HashSet<string> _excludedQuests = new(StringComparer.OrdinalIgnoreCase);

    public IReadOnlyList<QuestEntry> All => _all;
    public int Count => _all.Count;

    /// <summary>Zone lookup: scene_name → zone info (display name, level stats).</summary>
    public IReadOnlyDictionary<string, ZoneInfo> ZoneLookup { get; private set; } =
        new Dictionary<string, ZoneInfo>();

    /// <summary>Character spawns: stable_key → list of spawn points.</summary>
    public IReadOnlyDictionary<string, List<SpawnPoint>> CharacterSpawns { get; private set; } =
        new Dictionary<string, List<SpawnPoint>>();

    /// <summary>Zone transition points.</summary>
    public IReadOnlyList<ZoneLineEntry> ZoneLines { get; private set; } =
        Array.Empty<ZoneLineEntry>();

    /// <summary>Pre-computed quest chain groups.</summary>
    public IReadOnlyList<ChainGroupEntry> ChainGroups { get; private set; } =
        Array.Empty<ChainGroupEntry>();

    public IReadOnlyList<List<List<GateAtom>>> Conditions { get; private set; } =
        Array.Empty<List<List<GateAtom>>>();

    public IReadOnlyDictionary<string, GateItem> GateItems { get; private set; } =
        new Dictionary<string, GateItem>();

    public EncounterContext Encounters { get; private set; } = null!;
    public State.EncounterProjection EncounterProjection { get; private set; } = null!;

    /// <summary>Display names for furniture sets referenced by room conditions.</summary>
    public IReadOnlyDictionary<string, string> FurnitureSetNames { get; private set; } =
        new Dictionary<string, string>();

    private readonly Dictionary<string, Navigation.SpawnTiers> _encounterTiers = new(
        StringComparer.OrdinalIgnoreCase
    );

    /// <summary>The character's tier when the pipeline classifies it as a boss or an elite.</summary>
    internal Navigation.SpawnTiers EncounterTierOf(string characterStableKey) =>
        _encounterTiers.TryGetValue(characterStableKey, out var tier)
            ? tier
            : Navigation.SpawnTiers.None;

    public QuestEntry? GetByDBName(string dbName) =>
        _byDBName.TryGetValue(dbName, out var entry) ? entry : null;

    public QuestEntry? GetByStableKey(string stableKey) =>
        _byStableKey.TryGetValue(stableKey, out var entry) ? entry : null;

    /// <summary>Resolve a scene name to a display name via the zone lookup.</summary>
    public string? GetZoneDisplayName(string sceneName) =>
        ZoneLookup.TryGetValue(sceneName, out var info) ? info.DisplayName : null;

    /// <summary>Resolve a display zone name to a scene name. Inverse of GetZoneDisplayName.</summary>
    public string? GetSceneName(string displayName) =>
        _displayToScene.TryGetValue(displayName, out var scene) ? scene : null;

    public static GuideData Load(IModLogger log)
    {
        var assembly = Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream("AdventureGuide.quest-guide.json");
        if (stream == null)
        {
            log.LogError("Failed to load embedded quest-guide.json");
            throw new InvalidDataException("Failed to load embedded quest-guide.json");
        }

        // Deserialize straight from the resource stream. Reading the ~2 MB
        // file into a string first builds two UTF-16 copies of it at startup,
        // and the game's managed heap does not shrink back after such a peak.
        using var reader = new StreamReader(stream);
        using var json = new JsonTextReader(reader);
        var wrapper =
            JsonSerializer.CreateDefault().Deserialize<GuideWrapper>(json)
            ?? throw new InvalidDataException("Failed to deserialize quest-guide.json");
        return FromWrapper(wrapper);
    }

    internal static GuideData Parse(string json)
    {
        var wrapper =
            JsonConvert.DeserializeObject<GuideWrapper>(json)
            ?? throw new InvalidDataException("Failed to deserialize quest-guide.json");
        return FromWrapper(wrapper);
    }

    internal static GuideData FromWrapper(GuideWrapper wrapper)
    {
        ValidateWrapper(wrapper);

        var data = new GuideData();
        foreach (var entry in wrapper.Quests!)
        {
            data._all.Add(entry);
            data._byDBName.Add(entry.DBName, entry);
            data._byStableKey.Add(entry.StableKey, entry);
        }

        // Positioned source keys (mining:/water:/itembag:) carry lowercased
        // scene names, and scene comparisons elsewhere ignore case.
        data.ZoneLookup = new Dictionary<string, ZoneInfo>(
            wrapper.ZoneLookup ?? new Dictionary<string, ZoneInfo>(),
            StringComparer.OrdinalIgnoreCase
        );
        foreach (var (scene, info) in data.ZoneLookup)
            data._displayToScene[info.DisplayName] = scene;
        data.CharacterSpawns =
            wrapper.CharacterSpawns ?? new Dictionary<string, List<SpawnPoint>>();
        data.ZoneLines = wrapper.ZoneLines ?? new List<ZoneLineEntry>();
        data.ChainGroups = wrapper.ChainGroups ?? new List<ChainGroupEntry>();
        data.Conditions = wrapper.Conditions ?? new List<List<List<GateAtom>>>();
        data.GateItems = wrapper.GateItems ?? new Dictionary<string, GateItem>();
        var furnitureSetNames = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (wrapper.FurnitureSets != null)
        {
            foreach (var (key, set) in wrapper.FurnitureSets)
                furnitureSetNames[key] = set.DisplayName;
        }
        data.FurnitureSetNames = furnitureSetNames;
        if (wrapper.ExcludedQuests != null)
            data._excludedQuests.UnionWith(wrapper.ExcludedQuests);
        if (wrapper.EncounterTiers != null)
        {
            foreach (var (key, tier) in wrapper.EncounterTiers)
            {
                data._encounterTiers[key] = tier switch
                {
                    "boss" => Navigation.SpawnTiers.Boss,
                    "elite" => Navigation.SpawnTiers.Elite,
                    _ => throw new InvalidDataException(
                        $"Unknown encounter tier '{tier}' for {key}"
                    ),
                };
            }
        }

        data.Encounters = wrapper.Encounters!;
        data.EncounterProjection = new State.EncounterProjection(data, data.Encounters);
        data.LoadSourceFacts(wrapper);
        data.LoadDestinationContexts(wrapper);
        data.LoadActivations(wrapper);
        return data;
    }

    /// <summary>
    /// Whether a game quest belongs in the guide as a stub: unknown to the
    /// guide (a quest a game update added) and not deliberately excluded.
    /// </summary>
    internal bool ShouldStubUnknownQuest(string dbName) =>
        !_byDBName.ContainsKey(dbName) && !_excludedQuests.Contains(dbName);

    /// <summary>The quest-guide.json schema version that this build reads.</summary>
    internal const int SchemaVersion = 9;

    internal static void ValidateWrapper(GuideWrapper wrapper)
    {
        if (wrapper.Version != SchemaVersion)
            throw new InvalidDataException(
                $"Unsupported quest guide schema version {wrapper.Version}. Expected {SchemaVersion}"
            );
        if (wrapper.Quests == null)
            throw new InvalidDataException("Quest guide has no quests collection");

        var stableKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var dbNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var quest in wrapper.Quests)
        {
            if (string.IsNullOrWhiteSpace(quest.StableKey))
                throw new InvalidDataException("Quest has no stable key");
            if (string.IsNullOrWhiteSpace(quest.DBName))
                throw new InvalidDataException($"Quest {quest.StableKey} has no DB name");
            if (string.IsNullOrWhiteSpace(quest.DisplayName))
                throw new InvalidDataException($"Quest {quest.StableKey} has no display name");
            if (!stableKeys.Add(quest.StableKey))
                throw new InvalidDataException($"Duplicate quest stable key: {quest.StableKey}");
            if (!dbNames.Add(quest.DBName))
                throw new InvalidDataException($"Duplicate quest DB name: {quest.DBName}");

            ValidateSteps(quest);
        }

        foreach (var key in stableKeys)
        {
            if (dbNames.Contains(key))
                throw new InvalidDataException(
                    $"Quest identity collides across stable-key and DB-name namespaces: {key}"
                );
        }

        foreach (var quest in wrapper.Quests)
        {
            if (quest.Steps != null)
                foreach (var step in quest.Steps)
                    ValidateSources(step.Sources, step.TargetName ?? "", quest.StableKey);
            if (quest.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                    ValidateSources(item.Sources, item.ItemName, quest.StableKey);
        }

        ValidateConditions(wrapper);
        if (wrapper.Encounters == null)
            throw new InvalidDataException("Quest guide has no encounter payload");
        wrapper.Encounters.Validate(wrapper.Quests);
        ValidateSourceFacts(wrapper);
        ValidateDestinationContexts(wrapper);

        if (wrapper.ExcludedQuests != null)
        {
            foreach (var dbName in wrapper.ExcludedQuests)
            {
                if (dbNames.Contains(dbName))
                    throw new InvalidDataException(
                        $"Quest {dbName} is both excluded and in the guide"
                    );
            }
        }
    }

    private static void ValidateConditions(GuideWrapper wrapper)
    {
        var conditions = wrapper.Conditions ?? new List<List<List<GateAtom>>>();
        foreach (var groups in conditions)
        {
            foreach (var group in groups)
            {
                foreach (var atom in group)
                {
                    if (string.IsNullOrWhiteSpace(atom.Ref))
                        throw new InvalidDataException("Gate atom has no reference");
                    if (
                        atom.Quantity <= 0
                        || (atom.Kind != GateAtomKind.EncounterWon && atom.Quantity != 1)
                    )
                        throw new InvalidDataException("Invalid gate atom defeat quantity");
                    switch (atom.Kind)
                    {
                        case GateAtomKind.AccountState:
                            if (
                                atom.Ref != EncounterStateKeys.ReliquaryClaimed
                                || atom.Actor != "account"
                                || atom.Value is not ("true" or "false")
                                || atom.Phase != "availability"
                                || string.IsNullOrWhiteSpace(atom.Scope)
                            )
                                throw new InvalidDataException(
                                    "Invalid account-state availability atom"
                                );
                            break;
                        case GateAtomKind.ItemHeld:
                        case GateAtomKind.KeyHeld:
                        case GateAtomKind.RoomFurnished:
                        case GateAtomKind.PlanningSlotItem:
                            if (
                                wrapper.GateItems == null
                                || !wrapper.GateItems.TryGetValue(atom.Ref, out var item)
                            )
                                throw new InvalidDataException(
                                    $"Gate atom names unknown item {atom.Ref}"
                                );
                            atom.GameId = item.GameId;
                            if (
                                atom.Kind == GateAtomKind.RoomFurnished
                                && (atom.Slot == null || !FurnishingPolicy.IsRoomSlot(atom.Slot))
                            )
                                throw new InvalidDataException(
                                    $"Gate atom names unknown room {atom.Slot}"
                                );
                            if (
                                atom.Kind == GateAtomKind.PlanningSlotItem
                                && (
                                    atom.Slot == null || !FurnishingPolicy.IsPlanningSlot(atom.Slot)
                                )
                            )
                                throw new InvalidDataException(
                                    $"Gate atom names unknown planning slot {atom.Slot}"
                                );
                            if (
                                atom.Kind == GateAtomKind.PlanningSlotItem
                                && string.IsNullOrWhiteSpace(atom.Instruction)
                            )
                                throw new InvalidDataException(
                                    $"Planning slot atom has no instruction for {atom.Ref}"
                                );
                            break;
                        case GateAtomKind.QuestDone:
                        case GateAtomKind.QuestNotDone:
                        case GateAtomKind.EncounterWon:
                            break;
                        default:
                            throw new InvalidDataException($"Unknown gate atom kind {atom.Kind}");
                    }
                }
            }
        }

        void ValidateIndex(int? index)
        {
            if (index.HasValue && (index.Value < 0 || index.Value >= conditions.Count))
                throw new InvalidDataException($"Gate condition index {index} is out of range");
        }

        void ValidateSourceConditions(List<ItemSource>? sources)
        {
            if (sources == null)
                return;
            foreach (var source in sources)
            {
                ValidateIndex(source.Condition);
                ValidateSourceConditions(source.Children);
            }
        }

        if (wrapper.ZoneLines != null)
            foreach (var line in wrapper.ZoneLines)
                ValidateIndex(line.Condition);
        if (wrapper.CharacterSpawns != null)
            foreach (var spawns in wrapper.CharacterSpawns.Values)
            foreach (var spawn in spawns)
            {
                ValidateIndex(spawn.Condition);
                if (spawn.Entries == null)
                    continue;
                string? destinationKey = null;
                if (wrapper.ZoneLookup != null)
                    foreach (var zone in wrapper.ZoneLookup)
                        if (
                            string.Equals(zone.Key, spawn.Scene, StringComparison.OrdinalIgnoreCase)
                        )
                        {
                            destinationKey = zone.Value.StableKey;
                            break;
                        }
                foreach (int entry in spawn.Entries)
                {
                    if (wrapper.ZoneLines == null || entry < 0 || entry >= wrapper.ZoneLines.Count)
                        throw new InvalidDataException(
                            $"Spawn entry line index {entry} is out of range"
                        );
                    if (
                        wrapper.ZoneLineDestinationContexts?.ContainsKey(
                            wrapper.ZoneLines[entry].StableKey
                        ) == true
                    )
                        continue;
                    if (
                        destinationKey == null
                        || !string.Equals(
                            wrapper.ZoneLines[entry].DestinationZoneKey,
                            destinationKey,
                            StringComparison.OrdinalIgnoreCase
                        )
                    )
                        throw new InvalidDataException(
                            $"Spawn entry line {entry} does not enter {spawn.Scene}"
                        );
                }
            }
        foreach (var quest in wrapper.Quests!)
        {
            if (quest.Steps != null)
                foreach (var step in quest.Steps)
                    ValidateSourceConditions(step.Sources);
            if (quest.RequiredItems != null)
                foreach (var item in quest.RequiredItems)
                    ValidateSourceConditions(item.Sources);
        }
        if (wrapper.GateItems != null)
            foreach (var item in wrapper.GateItems.Values)
                ValidateSourceConditions(item.Sources);
    }

    private static void ValidateSteps(QuestEntry quest)
    {
        if (quest.Steps == null)
            return;
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.Order != i + 1)
                throw new InvalidDataException(
                    $"Quest {quest.StableKey} has non-consecutive step order"
                );
            if (
                string.IsNullOrWhiteSpace(step.Action)
                || string.IsNullOrWhiteSpace(step.Description)
            )
                throw new InvalidDataException(
                    $"Quest {quest.StableKey} has malformed step {step.Order}"
                );
        }
    }

    private static void ValidateSources(List<ItemSource>? sources, string itemName, string questKey)
    {
        if (sources == null)
            return;
        foreach (var source in sources)
        {
            if (
                source.Chance is double chance
                && (
                    double.IsNaN(chance) || double.IsInfinity(chance) || chance <= 0 || chance > 100
                )
            )
                throw new InvalidDataException($"{questKey} has invalid source chance");
            ValidateFishingChances(source, questKey);
            if (source.LevelMax is int max && (source.Level is not int min || max < min))
                throw new InvalidDataException($"{questKey} has invalid source level range");
            if (
                source.ChanceMax is double chanceMax
                && (
                    source.Chance is not double low
                    || double.IsNaN(chanceMax)
                    || double.IsInfinity(chanceMax)
                    || chanceMax < low
                    || chanceMax > 100
                )
            )
                throw new InvalidDataException($"{questKey} has invalid source chance range");
            if (ItemSourcePolicy.IsRandomSource(source) && string.IsNullOrWhiteSpace(source.Name))
                throw new InvalidDataException($"{questKey} has an unnamed random source");
            switch (source.Type)
            {
                case "world_drop":
                    if (source.Chance == null || source.Scene != null || source.SourceKey != null)
                        throw new InvalidDataException($"{questKey} has invalid world drop");
                    break;
                case "common_world_item":
                    if (
                        source.Chance == null
                        || source.ChanceMax == null
                        || source.Level != null
                        || source.Scene != null
                        || source.SourceKey != null
                    )
                        throw new InvalidDataException($"{questKey} has invalid common world item");
                    break;
                case "fishing_bonus":
                    if (
                        source.Chance == null
                        || source.Level != null
                        || source.Scene != null
                        || source.SourceKey != null
                    )
                        throw new InvalidDataException($"{questKey} has invalid fishing bonus");
                    break;
                case "treasure_chest":
                    if (
                        source.Chance == null
                        || source.Level is not >= 0
                        || source.LevelMax == null
                        || source.SourceKey?.StartsWith("character:", StringComparison.Ordinal)
                            != true
                        || string.IsNullOrWhiteSpace(source.Instruction)
                    )
                        throw new InvalidDataException($"{questKey} has invalid treasure chest");
                    break;
                case "item_use":
                    if (
                        source.SourceKey?.StartsWith("item:", StringComparison.Ordinal) != true
                        || string.IsNullOrWhiteSpace(source.Name)
                        || string.IsNullOrWhiteSpace(source.Instruction)
                        || source.Children == null
                    )
                        throw new InvalidDataException($"{questKey} has invalid item use");
                    break;
            }
            if (source.Type == "vendor" && source.Instruction != $"Buy {itemName}.")
                throw new InvalidDataException($"{questKey} has invalid vendor instruction");

            ValidateSources(
                source.Children,
                source.Type is "item_use" or "ingredient" ? source.Name! : itemName,
                questKey
            );
        }
    }

    private static void ValidateFishingChances(ItemSource source, string questKey)
    {
        if (source.Type != "fishing")
        {
            if (
                source.DayChance != null
                || source.NightChance != null
                || source.TimeRestriction != null
            )
                throw new InvalidDataException(
                    $"{questKey} has temporal chances on a non-fishing source"
                );
            return;
        }
        if (
            source.DayChance is not double day
            || source.NightChance is not double night
            || double.IsNaN(day)
            || double.IsInfinity(day)
            || double.IsNaN(night)
            || double.IsInfinity(night)
            || day < 0
            || night < 0
            || day > 100
            || night > 100
            || (day == 0 && night == 0)
        )
            throw new InvalidDataException($"{questKey} has invalid fishing phase chances");
        string? restriction =
            night == 0 ? "day"
            : day == 0 ? "night"
            : null;
        // Canonical acquisitions keep one identity per phase, with their own final odds.
        double? expectedChance =
            source.AcquisitionKey != null
                ? day > 0
                    ? day
                    : night
                : day == night
                    ? day
                    : null;
        if (
            source.TimeRestriction != restriction
            || source.Chance != expectedChance
            || source.AcquisitionKey == null && source.ChanceMax != null
            || source.AcquisitionKey != null && day > 0 && night > 0 && day != night
        )
            throw new InvalidDataException($"{questKey} has inconsistent fishing chances");
    }
}

/// <summary>Top-level JSON wrapper matching the Python GuideOutput structure.</summary>
internal sealed partial class GuideWrapper
{
    [JsonProperty("_version")]
    public int Version { get; set; }

    [JsonProperty("_zone_lookup")]
    public Dictionary<string, ZoneInfo>? ZoneLookup { get; set; }

    [JsonProperty("_character_spawns")]
    public Dictionary<string, List<SpawnPoint>>? CharacterSpawns { get; set; }

    [JsonProperty("_encounter_tiers")]
    public Dictionary<string, string>? EncounterTiers { get; set; }

    [JsonProperty("_zone_lines")]
    public List<ZoneLineEntry>? ZoneLines { get; set; }

    [JsonProperty("_chain_groups")]
    public List<ChainGroupEntry>? ChainGroups { get; set; }

    [JsonProperty("_conditions")]
    public List<List<List<GateAtom>>>? Conditions { get; set; }

    [JsonProperty("_gate_items")]
    public Dictionary<string, GateItem>? GateItems { get; set; }

    [JsonProperty("_furniture_sets")]
    public Dictionary<string, FurnitureSetInfo>? FurnitureSets { get; set; }

    [JsonProperty("_encounters")]
    public EncounterContext? Encounters { get; set; }

    [JsonProperty("_excluded_quests")]
    public List<string>? ExcludedQuests { get; set; }

    [JsonProperty("quests")]
    public List<QuestEntry>? Quests { get; set; }
}

/// <summary>Zone metadata from the lookup table.</summary>
public sealed class ZoneInfo
{
    [JsonProperty("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonProperty("stable_key")]
    public string StableKey { get; set; } = "";

    [JsonProperty("level_min")]
    public int? LevelMin { get; set; }

    [JsonProperty("level_max")]
    public int? LevelMax { get; set; }

    [JsonProperty("level_median")]
    public int? LevelMedian { get; set; }
}

/// <summary>A Reliquary furniture set that places furnishing characters.</summary>
public sealed class FurnitureSetInfo
{
    [JsonProperty("display_name")]
    public string DisplayName { get; set; } = "";
}

/// <summary>A character spawn point with coordinates.</summary>
public sealed class SpawnPoint
{
    [JsonProperty("stable_key")]
    public string StableKey { get; set; } = "";

    [JsonProperty("scene")]
    public string Scene { get; set; } = "";

    [JsonProperty("x")]
    public float X { get; set; }

    [JsonProperty("y")]
    public float Y { get; set; }

    [JsonProperty("z")]
    public float Z { get; set; }

    [JsonProperty("night_spawn")]
    public bool NightSpawn { get; set; }

    [JsonProperty("condition")]
    public int? Condition { get; set; }

    [JsonProperty("entries")]
    public List<int>? Entries { get; set; }

    [JsonProperty("is_directly_placed")]
    public bool IsDirectlyPlaced { get; set; }

    [JsonProperty("source_script")]
    public string? SourceScript { get; set; }

    [JsonProperty("activations")]
    public List<ActivationReference>? Activations { get; set; }
}

/// <summary>A zone transition point.</summary>
public sealed class ZoneLineEntry
{
    [JsonProperty("stable_key")]
    public string StableKey { get; set; } = "";

    [JsonProperty("scene")]
    public string Scene { get; set; } = "";

    [JsonProperty("x")]
    public float X { get; set; }

    [JsonProperty("y")]
    public float Y { get; set; }

    [JsonProperty("z")]
    public float Z { get; set; }

    [JsonProperty("destination_zone_key")]
    public string DestinationZoneKey { get; set; } = "";

    [JsonProperty("destination_display")]
    public string DestinationDisplay { get; set; } = "";

    [JsonProperty("landing_x")]
    public float? LandingX { get; set; }

    [JsonProperty("landing_y")]
    public float? LandingY { get; set; }

    [JsonProperty("landing_z")]
    public float? LandingZ { get; set; }

    [JsonProperty("condition")]
    public int? Condition { get; set; }
}

/// <summary>A pre-computed quest chain group.</summary>
public sealed class ChainGroupEntry
{
    [JsonProperty("name")]
    public string Name { get; set; } = "";

    [JsonProperty("quests")]
    public List<string> Quests { get; set; } = new();
}

using System.Reflection;
using Lunaris;
using Newtonsoft.Json;

namespace AdventureGuide.Data;

/// <summary>
/// Loads and holds the quest guide database from the embedded JSON resource.
/// The JSON has a wrapper structure with lookup tables and a quests array.
/// </summary>
public sealed class GuideData
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

    /// <summary>Character quest unlock requirements: stable_key → OR-of-ANDs quest groups.</summary>
    public IReadOnlyDictionary<string, List<List<string>>> CharacterQuestUnlocks
    {
        get;
        private set;
    } = new Dictionary<string, List<List<string>>>();

    public QuestEntry? GetByDBName(string dbName) =>
        _byDBName.TryGetValue(dbName, out var entry) ? entry : null;

    public QuestEntry? GetByStableKey(string stableKey) =>
        _byStableKey.TryGetValue(stableKey, out var entry) ? entry : null;

    public QuestEntry? GetByRuntimeKey(string key) =>
        _byStableKey.TryGetValue(key, out var stableEntry) ? stableEntry
        : _byDBName.TryGetValue(key, out var dbEntry) ? dbEntry
        : null;

    /// <summary>Resolve a scene name to a display name via the zone lookup.</summary>
    public string? GetZoneDisplayName(string sceneName) =>
        ZoneLookup.TryGetValue(sceneName, out var info) ? info.DisplayName : null;

    /// <summary>Resolve a display zone name to a scene name. Inverse of GetZoneDisplayName.</summary>
    public string? GetSceneName(string displayName) =>
        _displayToScene.TryGetValue(displayName, out var scene) ? scene : null;

    public static GuideData Load(ILog log)
    {
        var assembly = Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream("AdventureGuide.quest-guide.json");
        if (stream == null)
        {
            log.LogError("Failed to load embedded quest-guide.json");
            return new GuideData();
        }

        using var reader = new StreamReader(stream);
        return Parse(reader.ReadToEnd());
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

        data.ZoneLookup = wrapper.ZoneLookup ?? new Dictionary<string, ZoneInfo>();
        foreach (var (scene, info) in data.ZoneLookup)
            data._displayToScene[info.DisplayName] = scene;
        data.CharacterSpawns =
            wrapper.CharacterSpawns ?? new Dictionary<string, List<SpawnPoint>>();
        data.ZoneLines = wrapper.ZoneLines ?? new List<ZoneLineEntry>();
        data.ChainGroups = wrapper.ChainGroups ?? new List<ChainGroupEntry>();
        data.CharacterQuestUnlocks =
            wrapper.CharacterQuestUnlocks ?? new Dictionary<string, List<List<string>>>();

        return data;
    }

    internal static void ValidateWrapper(GuideWrapper wrapper)
    {
        if (wrapper.Version != 6)
            throw new InvalidDataException(
                $"Unsupported quest guide schema version {wrapper.Version}; expected 6"
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
            if (quest.IsGuideOnly)
                ValidateWorkflow(quest);
            else if (quest.WorkflowCycle != null)
                throw new InvalidDataException(
                    $"Game quest {quest.StableKey} has workflow metadata"
                );
        }

        foreach (var key in stableKeys)
        {
            if (dbNames.Contains(key))
                throw new InvalidDataException(
                    $"Quest identity collides across stable-key and DB-name namespaces: {key}"
                );
        }

        var gameDbNames = new HashSet<string>(
            wrapper.Quests.Where(quest => !quest.IsGuideOnly).Select(quest => quest.DBName),
            StringComparer.OrdinalIgnoreCase
        );
        foreach (var quest in wrapper.Quests)
        {
            if (quest.RequiredItems == null)
                continue;
            foreach (var item in quest.RequiredItems)
                ValidateSources(item.Sources, item.ItemName, gameDbNames, quest.StableKey);
        }
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
            if (step.Action == "go_to")
                ValidateLocation(
                    step.Location,
                    requireBounds: false,
                    $"{quest.StableKey} step {step.Order}"
                );
        }
    }

    private static void ValidateWorkflow(QuestEntry quest)
    {
        if (
            !quest.IsImplicit
            || quest.Flags is not { Repeatable: true }
            || quest.WorkflowCycle == null
        )
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has invalid lifecycle"
            );
        var steps = quest.Steps;
        if (steps == null || steps.Count < 3)
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has no workflow steps"
            );

        var cycle = quest.WorkflowCycle;
        var trigger = cycle.Trigger;
        if (
            string.IsNullOrWhiteSpace(trigger.ItemStableKey)
            || string.IsNullOrWhiteSpace(trigger.ItemName)
            || trigger.Quantity <= 0
            || trigger.Mode != "proximity_auto_consume"
            || !trigger.ConsumesItemAutomatically
        )
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has invalid trigger"
            );
        ValidateLocation(trigger.Location, requireBounds: true, $"{quest.StableKey} trigger");

        var targetKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (cycle.Targets.Count == 0)
            throw new InvalidDataException($"Guide-only quest {quest.StableKey} has no targets");
        foreach (var target in cycle.Targets)
        {
            if (
                string.IsNullOrWhiteSpace(target.StableKey)
                || string.IsNullOrWhiteSpace(target.DisplayName)
                || target.Quantity <= 0
                || !targetKeys.Add(target.StableKey)
            )
                throw new InvalidDataException(
                    $"Guide-only quest {quest.StableKey} has invalid targets"
                );
        }

        bool targetReset = cycle.ResetEvidence == "targets_defeated";
        bool rewardReset = cycle.ResetEvidence == "reward_container_consumed";
        if (!targetReset && !rewardReset)
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has invalid reset evidence"
            );
        if ((cycle.RewardContainer == null) != targetReset)
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has inconsistent reward evidence"
            );
        if (
            cycle.RewardContainer != null
            && (
                string.IsNullOrWhiteSpace(cycle.RewardContainer.StableKey)
                || string.IsNullOrWhiteSpace(cycle.RewardContainer.DisplayName)
            )
        )
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has invalid reward container"
            );

        var obtainStep = steps[0];
        var goToStep = steps[1];
        if (
            obtainStep.Action != "obtain"
            || obtainStep.TargetType != "item"
            || !string.Equals(
                obtainStep.TargetKey,
                trigger.ItemStableKey,
                StringComparison.OrdinalIgnoreCase
            )
            || obtainStep.Quantity != trigger.Quantity
            || goToStep.Action != "go_to"
            || goToStep.TargetType != "location"
            || !string.Equals(
                goToStep.TargetKey,
                trigger.Location.StableKey,
                StringComparison.OrdinalIgnoreCase
            )
        )
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has invalid workflow step order"
            );

        var triggerStepLocation = goToStep.Location;
        if (
            triggerStepLocation == null
            || !string.Equals(
                triggerStepLocation.StableKey,
                trigger.Location.StableKey,
                StringComparison.OrdinalIgnoreCase
            )
            || !string.Equals(
                triggerStepLocation.Scene,
                trigger.Location.Scene,
                StringComparison.OrdinalIgnoreCase
            )
        )
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has inconsistent trigger location"
            );

        var expectedKills = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (var target in cycle.Targets)
        {
            var group = CharacterStableKey.Normalize(target.StableKey);
            expectedKills[group] = expectedKills.TryGetValue(group, out int count)
                ? count + target.Quantity
                : target.Quantity;
        }

        var stepKills = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        int lootSteps = 0;
        for (int i = 2; i < steps.Count; i++)
        {
            var step = steps[i];
            if (step.Action == "loot")
            {
                lootSteps++;
                continue;
            }
            if (
                step.Action != "kill"
                || string.IsNullOrWhiteSpace(step.TargetKey)
                || step.TargetType != "character"
                || step.Quantity is null or <= 0
            )
                throw new InvalidDataException(
                    $"Guide-only quest {quest.StableKey} has unsupported action {step.Action}"
                );
            var group = CharacterStableKey.Normalize(step.TargetKey);
            stepKills[group] = stepKills.TryGetValue(group, out int count)
                ? count + step.Quantity.Value
                : step.Quantity.Value;
        }

        if (
            stepKills.Count != expectedKills.Count
            || expectedKills.Any(expected =>
                !stepKills.TryGetValue(expected.Key, out int count) || count != expected.Value
            )
        )
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has inconsistent targets"
            );

        if (targetReset && lootSteps != 0)
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has unexpected reward loot step"
            );
        if (
            rewardReset
            && (
                lootSteps != 1
                || steps[^1].Action != "loot"
                || !string.Equals(
                    steps[^1].TargetKey,
                    cycle.RewardContainer!.StableKey,
                    StringComparison.OrdinalIgnoreCase
                )
            )
        )
            throw new InvalidDataException(
                $"Guide-only quest {quest.StableKey} has invalid reward loot step"
            );
    }

    private static void ValidateLocation(
        WorkflowLocation? location,
        bool requireBounds,
        string context
    )
    {
        if (
            location == null
            || string.IsNullOrWhiteSpace(location.StableKey)
            || string.IsNullOrWhiteSpace(location.DisplayName)
            || string.IsNullOrWhiteSpace(location.Scene)
            || !IsFinite(location.X)
            || !IsFinite(location.Y)
            || !IsFinite(location.Z)
        )
            throw new InvalidDataException($"{context} has invalid location");
        if (!requireBounds)
            return;
        if (
            location.Bounds == null
            || !IsFinite(location.Bounds.Center.X)
            || !IsFinite(location.Bounds.Center.Y)
            || !IsFinite(location.Bounds.Center.Z)
            || !IsFinite(location.Bounds.Extents.X)
            || !IsFinite(location.Bounds.Extents.Y)
            || !IsFinite(location.Bounds.Extents.Z)
            || location.Bounds.Extents.X <= 0f
            || location.Bounds.Extents.Y <= 0f
            || location.Bounds.Extents.Z <= 0f
        )
            throw new InvalidDataException($"{context} has invalid trigger bounds");
    }

    private static void ValidateSources(
        List<ItemSource>? sources,
        string itemName,
        HashSet<string> gameDbNames,
        string questKey
    )
    {
        if (sources == null)
            return;
        foreach (var source in sources)
        {
            if (source.Type == "vendor" && source.Instruction != $"Buy {itemName}.")
                throw new InvalidDataException($"{questKey} has invalid vendor instruction");

            if (source.RequiredQuestDBNames != null)
            {
                if (source.RequiredQuestDBNames.Count == 0)
                    throw new InvalidDataException($"{questKey} has an empty source gate");
                var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (var dbName in source.RequiredQuestDBNames)
                {
                    if (!seen.Add(dbName) || !gameDbNames.Contains(dbName))
                        throw new InvalidDataException(
                            $"{questKey} references invalid source unlock quest {dbName}"
                        );
                }
            }
            ValidateSources(source.Children, itemName, gameDbNames, questKey);
        }
    }

    private static bool IsFinite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

    /// <summary>
    /// Scan the game's QuestDB for quests not in the guide and create
    /// stub entries with name and description. Returns the number of
    /// quests discovered.
    /// Returns the count of discovered quests, or -1 if QuestDB
    /// is not yet available (caller should retry later).
    /// </summary>
    public int MergeUnknownQuests()
    {
        var db = GameData.QuestDB;
        if (db == null || db.QuestDatabase == null)
            return -1;

        int count = 0;
        foreach (var quest in db.QuestDatabase)
        {
            if (quest == null)
                continue;
            if (string.IsNullOrEmpty(quest.DBName))
                continue;
            if (_byDBName.ContainsKey(quest.DBName))
                continue;

            var stub = new QuestEntry
            {
                DBName = quest.DBName,
                DisplayName = quest.QuestName ?? quest.DBName,
                Description = quest.QuestDesc,
            };
            _all.Add(stub);
            _byDBName[stub.DBName] = stub;
            count++;
        }
        return count;
    }
}

/// <summary>Top-level JSON wrapper matching the Python GuideOutput structure.</summary>
internal sealed class GuideWrapper
{
    [JsonProperty("_version")]
    public int Version { get; set; }

    [JsonProperty("_zone_lookup")]
    public Dictionary<string, ZoneInfo>? ZoneLookup { get; set; }

    [JsonProperty("_character_spawns")]
    public Dictionary<string, List<SpawnPoint>>? CharacterSpawns { get; set; }

    [JsonProperty("_zone_lines")]
    public List<ZoneLineEntry>? ZoneLines { get; set; }

    [JsonProperty("_chain_groups")]
    public List<ChainGroupEntry>? ChainGroups { get; set; }

    [JsonProperty("_character_quest_unlocks")]
    public Dictionary<string, List<List<string>>>? CharacterQuestUnlocks { get; set; }

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

/// <summary>A character spawn point with coordinates.</summary>
public sealed class SpawnPoint
{
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

    [JsonProperty("spawn_upon_quest_complete_stable_key")]
    public string? SpawnUponQuestCompleteStableKey { get; set; }

    [JsonProperty("is_directly_placed")]
    public bool IsDirectlyPlaced { get; set; }

    [JsonProperty("source_script")]
    public string? SourceScript { get; set; }
}

/// <summary>A zone transition point.</summary>
public sealed class ZoneLineEntry
{
    [JsonProperty("scene")]
    public string Scene { get; set; } = "";

    [JsonProperty("x")]
    public float X { get; set; }

    [JsonProperty("y")]
    public float Y { get; set; }

    [JsonProperty("z")]
    public float Z { get; set; }

    [JsonProperty("is_enabled")]
    public bool IsEnabled { get; set; } = true;

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

    [JsonProperty("required_quest_groups")]
    public List<List<string>>? RequiredQuestGroups { get; set; }
}

/// <summary>A pre-computed quest chain group.</summary>
public sealed class ChainGroupEntry
{
    [JsonProperty("name")]
    public string Name { get; set; } = "";

    [JsonProperty("quests")]
    public List<string> Quests { get; set; } = new();
}

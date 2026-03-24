using System.Reflection;
using BepInEx.Logging;
using Newtonsoft.Json;

namespace AdventureGuide.Data;

/// <summary>
/// Loads and holds the quest guide database from the embedded JSON resource.
/// The JSON has a wrapper structure with lookup tables and a quests array.
/// </summary>
public sealed class GuideData
{
    private readonly Dictionary<string, QuestEntry> _byDBName = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, QuestEntry> _byStableKey = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<QuestEntry> _all = new();
    private readonly Dictionary<string, string> _displayToScene = new(StringComparer.OrdinalIgnoreCase);

    public IReadOnlyList<QuestEntry> All => _all;
    public int Count => _all.Count;

    /// <summary>Zone lookup: scene_name → zone info (display name, level stats).</summary>
    public IReadOnlyDictionary<string, ZoneInfo> ZoneLookup { get; private set; }
        = new Dictionary<string, ZoneInfo>();

    /// <summary>Character spawns: stable_key → list of spawn points.</summary>
    public IReadOnlyDictionary<string, List<SpawnPoint>> CharacterSpawns { get; private set; }
        = new Dictionary<string, List<SpawnPoint>>();

    /// <summary>Zone transition points.</summary>
    public IReadOnlyList<ZoneLineEntry> ZoneLines { get; private set; }
        = Array.Empty<ZoneLineEntry>();

    /// <summary>Pre-computed quest chain groups.</summary>
    public IReadOnlyList<ChainGroupEntry> ChainGroups { get; private set; }
        = Array.Empty<ChainGroupEntry>();

    /// <summary>Character quest unlock requirements: stable_key → OR-of-ANDs quest groups.</summary>
    public IReadOnlyDictionary<string, List<List<string>>> CharacterQuestUnlocks { get; private set; }
        = new Dictionary<string, List<List<string>>>();

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

    public static GuideData Load(ManualLogSource log)
    {
        var data = new GuideData();
        var assembly = Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream("AdventureGuide.quest-guide.json");
        if (stream == null)
        {
            log.LogError("Failed to load embedded quest-guide.json");
            return data;
        }

        using var reader = new StreamReader(stream);
        var json = reader.ReadToEnd();

        var wrapper = JsonConvert.DeserializeObject<GuideWrapper>(json);
        if (wrapper == null)
        {
            log.LogError("Failed to deserialize quest-guide.json");
            return data;
        }

        // Populate quest indexes
        if (wrapper.Quests != null)
        {
            foreach (var entry in wrapper.Quests)
            {
                data._all.Add(entry);
                data._byDBName[entry.DBName] = entry;
                data._byStableKey[entry.StableKey] = entry;
            }
        }

        // Populate lookup tables
        data.ZoneLookup = wrapper.ZoneLookup ?? new Dictionary<string, ZoneInfo>();
        foreach (var (scene, info) in data.ZoneLookup)
            data._displayToScene[info.DisplayName] = scene;
        data.CharacterSpawns = wrapper.CharacterSpawns ?? new Dictionary<string, List<SpawnPoint>>();
        data.ZoneLines = wrapper.ZoneLines ?? new List<ZoneLineEntry>();
        data.ChainGroups = wrapper.ChainGroups ?? new List<ChainGroupEntry>();
        data.CharacterQuestUnlocks = wrapper.CharacterQuestUnlocks ?? new Dictionary<string, List<List<string>>>();

        log.LogInfo($"Loaded {data.Count} quest guide entries "
            + $"({data.ZoneLookup.Count} zones, "
            + $"{data.CharacterSpawns.Count} character spawns, "
            + $"{data.ZoneLines.Count} zone lines, "
            + $"{data.ChainGroups.Count} chain groups)");
        return data;
    }
}

/// <summary>Top-level JSON wrapper matching the Python GuideOutput structure.</summary>
internal sealed class GuideWrapper
{
    [JsonProperty("_version")] public int Version { get; set; }
    [JsonProperty("_zone_lookup")] public Dictionary<string, ZoneInfo>? ZoneLookup { get; set; }
    [JsonProperty("_character_spawns")] public Dictionary<string, List<SpawnPoint>>? CharacterSpawns { get; set; }
    [JsonProperty("_zone_lines")] public List<ZoneLineEntry>? ZoneLines { get; set; }
    [JsonProperty("_chain_groups")] public List<ChainGroupEntry>? ChainGroups { get; set; }
    [JsonProperty("_character_quest_unlocks")] public Dictionary<string, List<List<string>>>? CharacterQuestUnlocks { get; set; }
    [JsonProperty("quests")] public List<QuestEntry>? Quests { get; set; }
}

/// <summary>Zone metadata from the lookup table.</summary>
public sealed class ZoneInfo
{
    [JsonProperty("display_name")] public string DisplayName { get; set; } = "";
    [JsonProperty("stable_key")] public string StableKey { get; set; } = "";
    [JsonProperty("level_min")] public int? LevelMin { get; set; }
    [JsonProperty("level_max")] public int? LevelMax { get; set; }
    [JsonProperty("level_median")] public int? LevelMedian { get; set; }
}

/// <summary>A character spawn point with coordinates.</summary>
public sealed class SpawnPoint
{
    [JsonProperty("scene")] public string Scene { get; set; } = "";
    [JsonProperty("x")] public float X { get; set; }
    [JsonProperty("y")] public float Y { get; set; }
    [JsonProperty("z")] public float Z { get; set; }
    [JsonProperty("night_spawn")] public bool NightSpawn { get; set; }
}

/// <summary>A zone transition point.</summary>
public sealed class ZoneLineEntry
{
    [JsonProperty("scene")] public string Scene { get; set; } = "";
    [JsonProperty("x")] public float X { get; set; }
    [JsonProperty("y")] public float Y { get; set; }
    [JsonProperty("z")] public float Z { get; set; }
    [JsonProperty("is_enabled")] public bool IsEnabled { get; set; } = true;
    [JsonProperty("destination_zone_key")] public string DestinationZoneKey { get; set; } = "";
    [JsonProperty("destination_display")] public string DestinationDisplay { get; set; } = "";
    [JsonProperty("landing_x")] public float? LandingX { get; set; }
    [JsonProperty("landing_y")] public float? LandingY { get; set; }
    [JsonProperty("landing_z")] public float? LandingZ { get; set; }
    [JsonProperty("required_quest_groups")] public List<List<string>>? RequiredQuestGroups { get; set; }
}

/// <summary>A pre-computed quest chain group.</summary>
public sealed class ChainGroupEntry
{
    [JsonProperty("name")] public string Name { get; set; } = "";
    [JsonProperty("quests")] public List<string> Quests { get; set; } = new();
}

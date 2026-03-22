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

    public IReadOnlyList<QuestEntry> All => _all;
    public int Count => _all.Count;

    /// <summary>Zone lookup: scene_name → zone info (display name, level stats).</summary>
    public IReadOnlyDictionary<string, ZoneInfo> ZoneLookup { get; private set; }
        = new Dictionary<string, ZoneInfo>();

    /// <summary>Character spawns: stable_key → list of spawn points.</summary>
    public IReadOnlyDictionary<string, List<SpawnPoint>> CharacterSpawns { get; private set; }
        = new Dictionary<string, List<SpawnPoint>>();

    /// <summary>
    /// Reverse index: lowercase character display name → stable keys that match.
    /// Built once at load time from CharacterSpawns keys. Handles both
    /// "character:name" and "character:name:scene:x:y:z" key formats.
    /// </summary>
    public IReadOnlyDictionary<string, List<string>> CharacterNameToKeys { get; private set; }
        = new Dictionary<string, List<string>>();

    /// <summary>Zone transition points.</summary>
    public IReadOnlyList<ZoneLineEntry> ZoneLines { get; private set; }
        = Array.Empty<ZoneLineEntry>();

    /// <summary>Pre-computed quest chain groups.</summary>
    public IReadOnlyList<ChainGroupEntry> ChainGroups { get; private set; }
        = Array.Empty<ChainGroupEntry>();

    public QuestEntry? GetByDBName(string dbName) =>
        _byDBName.TryGetValue(dbName, out var entry) ? entry : null;

    public QuestEntry? GetByStableKey(string stableKey) =>
        _byStableKey.TryGetValue(stableKey, out var entry) ? entry : null;

    /// <summary>Resolve a scene name to a display name via the zone lookup.</summary>
    public string? GetZoneDisplayName(string sceneName) =>
        ZoneLookup.TryGetValue(sceneName, out var info) ? info.DisplayName : null;

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
        data.CharacterSpawns = wrapper.CharacterSpawns ?? new Dictionary<string, List<SpawnPoint>>();
        data.ZoneLines = wrapper.ZoneLines ?? new List<ZoneLineEntry>();
        data.ChainGroups = wrapper.ChainGroups ?? new List<ChainGroupEntry>();

        // Build reverse name → key index for navigation lookup
        data.CharacterNameToKeys = BuildCharacterNameIndex(data.CharacterSpawns);

        log.LogInfo($"Loaded {data.Count} quest guide entries "
            + $"({data.ZoneLookup.Count} zones, "
            + $"{data.CharacterSpawns.Count} character spawns, "
            + $"{data.ZoneLines.Count} zone lines, "
            + $"{data.ChainGroups.Count} chain groups)");
        return data;
    }

    /// <summary>
    /// Extract display name from a character_spawns key. Handles both
    /// "character:name" and "character:name:scene:x:y:z" formats.
    /// Returns the name portion lowercased.
    /// </summary>
    private static string? ExtractNameFromKey(string key)
    {
        int colonIdx = key.IndexOf(':');
        if (colonIdx < 0) return null;
        string rest = key.Substring(colonIdx + 1);
        // Complex keys have additional colon-separated scene:x:y:z
        // but the name itself may contain colons (unlikely for character names).
        // The scene segment always starts with an uppercase letter (scene names
        // are PascalCase). Character names are lowercase in keys.
        // Simple heuristic: split on ':' and take segments until one parses as float.
        var parts = rest.Split(':');
        if (parts.Length <= 1) return rest;
        // For complex keys like "character:name:SceneName:x:y:z", take just parts[0]
        // since all character names in the data are single colon-separated.
        return parts[0];
    }

    private static Dictionary<string, List<string>> BuildCharacterNameIndex(
        IReadOnlyDictionary<string, List<SpawnPoint>> spawns)
    {
        var index = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        foreach (var key in spawns.Keys)
        {
            string? name = ExtractNameFromKey(key);
            if (name == null) continue;
            if (!index.TryGetValue(name, out var keys))
            {
                keys = new List<string>();
                index[name] = keys;
            }
            keys.Add(key);
        }
        return index;
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
}

/// <summary>A zone transition point.</summary>
public sealed class ZoneLineEntry
{
    [JsonProperty("scene")] public string Scene { get; set; } = "";
    [JsonProperty("x")] public float X { get; set; }
    [JsonProperty("y")] public float Y { get; set; }
    [JsonProperty("z")] public float Z { get; set; }
    [JsonProperty("destination_zone_key")] public string DestinationZoneKey { get; set; } = "";
    [JsonProperty("destination_display")] public string DestinationDisplay { get; set; } = "";
    [JsonProperty("landing_x")] public float? LandingX { get; set; }
    [JsonProperty("landing_y")] public float? LandingY { get; set; }
    [JsonProperty("landing_z")] public float? LandingZ { get; set; }
}

/// <summary>A pre-computed quest chain group.</summary>
public sealed class ChainGroupEntry
{
    [JsonProperty("name")] public string Name { get; set; } = "";
    [JsonProperty("quests")] public List<string> Quests { get; set; } = new();
}

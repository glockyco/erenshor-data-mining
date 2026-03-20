using System.Reflection;
using BepInEx.Logging;
using Newtonsoft.Json;

namespace AdventureGuide.Data;

/// <summary>
/// Loads and holds the quest guide database from the embedded JSON resource.
/// </summary>
public sealed class GuideData
{
    private readonly Dictionary<string, QuestEntry> _byDBName = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, QuestEntry> _byStableKey = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<QuestEntry> _all = new();

    public IReadOnlyList<QuestEntry> All => _all;
    public int Count => _all.Count;

    public QuestEntry? GetByDBName(string dbName) =>
        _byDBName.TryGetValue(dbName, out var entry) ? entry : null;

    public QuestEntry? GetByStableKey(string stableKey) =>
        _byStableKey.TryGetValue(stableKey, out var entry) ? entry : null;

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
        var entries = JsonConvert.DeserializeObject<List<QuestEntry>>(json);
        if (entries == null)
        {
            log.LogError("Failed to deserialize quest-guide.json");
            return data;
        }

        foreach (var entry in entries)
        {
            data._all.Add(entry);
            data._byDBName[entry.DBName] = entry;
            data._byStableKey[entry.StableKey] = entry;
        }

        log.LogInfo($"Loaded {data.Count} quest guide entries");
        return data;
    }
}

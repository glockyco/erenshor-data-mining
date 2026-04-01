using Newtonsoft.Json;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Captures the complete pipeline-relevant game state as a JSON-serializable snapshot.
/// Combined with entity-graph.json, this fully determines the canonical plan,
/// frontier, and unlock outputs for a quest.
/// </summary>
public sealed class StateSnapshot
{
    [JsonProperty("version")] public int Version { get; set; } = 1;
    [JsonProperty("captured_at")] public string? CapturedAt { get; set; }
    [JsonProperty("current_zone")] public string CurrentZone { get; set; } = "";
    [JsonProperty("active_quests")] public List<string> ActiveQuests { get; set; } = new();
    [JsonProperty("completed_quests")] public List<string> CompletedQuests { get; set; } = new();
    [JsonProperty("inventory")] public Dictionary<string, int> Inventory { get; set; } = new();
    [JsonProperty("keyring")] public List<string> Keyring { get; set; } = new();
    [JsonProperty("live_node_states")] public Dictionary<string, LiveNodeState> LiveNodeStates { get; set; } = new();
}

public sealed class LiveNodeState
{
    [JsonProperty("state")] public string State { get; set; } = "unknown";
    [JsonProperty("is_satisfied")] public bool IsSatisfied { get; set; }
}

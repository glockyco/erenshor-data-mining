using Newtonsoft.Json;

namespace AdventureGuide.Data;

public sealed class EncounterContext
{
    // JsonRequired rejects missing/null values without enum metadata that Lunaris cannot scan.
    [JsonProperty("encounter_placements"), JsonRequired]
    public List<EncounterPlacement> Placements { get; set; } = null!;

    [JsonProperty("encounter_conditions"), JsonRequired]
    public List<EncounterCondition> Conditions { get; set; } = null!;

    [JsonProperty("encounter_completions"), JsonRequired]
    public List<EncounterCompletion> Completions { get; set; } = null!;

    [JsonProperty("encounter_event_conditions"), JsonRequired]
    public List<EncounterEventCondition> EventConditions { get; set; } = null!;

    internal void Validate(IReadOnlyList<QuestEntry> quests)
    {
        if (
            Placements == null
            || Conditions == null
            || Completions == null
            || EventConditions == null
        )
            throw new InvalidDataException("Encounter payload requires all four row families");

        var roots = new Dictionary<string, string>(StringComparer.Ordinal);
        var members = new HashSet<(string, string)>();
        foreach (var row in Placements)
        {
            ValidateIdentity(row);
            if (row.ContextKind != "account_claim" || row.PostCompletionRole != "player_home")
                throw new InvalidDataException("Invalid encounter purpose metadata");
            if (
                string.IsNullOrWhiteSpace(row.RootSpawnStableKey)
                || string.IsNullOrWhiteSpace(row.MemberSpawnStableKey)
                || row.Role is not ("root" or "support")
                || (row.Role == "root") != (row.RootSpawnStableKey == row.MemberSpawnStableKey)
                || !members.Add((row.EncounterKey, row.MemberSpawnStableKey))
            )
                throw new InvalidDataException("Invalid or duplicate encounter placement");
            if (roots.TryGetValue(row.EncounterKey, out var root) && root != row.RootSpawnStableKey)
                throw new InvalidDataException("Encounter members disagree on root identity");
            roots[row.EncounterKey] = row.RootSpawnStableKey;
        }
        foreach (var pair in roots)
            if (!members.Contains((pair.Key, pair.Value)))
                throw new InvalidDataException("Encounter has no root placement");

        var conditionKeys = new HashSet<(string, string, string)>();
        foreach (var row in Conditions)
        {
            ValidateIdentity(row);
            ValidateState(row, row.StateScope, row.StateKey, row.RequiredValue);
            if (!conditionKeys.Add((row.EncounterKey, row.StateScope, row.StateKey)))
                throw new InvalidDataException("Duplicate encounter condition");
        }
        var effects = new HashSet<(string, string, string, string)>();
        var events = new HashSet<(string, string)>();
        foreach (var row in Completions)
        {
            ValidateIdentity(row);
            ValidateState(row, row.StateScope, row.StateKey, row.ResultValue);
            ValidateEvent(row.EventKind);
            if (!effects.Add((row.EncounterKey, row.EventKind, row.StateScope, row.StateKey)))
                throw new InvalidDataException("Duplicate encounter completion");
            events.Add((row.EncounterKey, row.EventKind));
        }
        var guards = new HashSet<(string, string, string, string)>();
        foreach (var row in EventConditions)
        {
            ValidateIdentity(row);
            ValidateState(row, row.StateScope, row.StateKey, row.RequiredValue);
            ValidateEvent(row.EventKind);
            if (
                !events.Contains((row.EncounterKey, row.EventKind))
                || !guards.Add((row.EncounterKey, row.EventKind, row.StateScope, row.StateKey))
            )
                throw new InvalidDataException("Unbound or duplicate encounter event guard");
        }
        foreach (string encounter in roots.Keys)
        {
            var conditions = Conditions
                .Where(row => row.EncounterKey == encounter)
                .Select(row => (row.StateScope, row.StateKey, row.RequiredValue))
                .ToHashSet();
            var character = conditions.Where(state => state.StateScope == "character").ToArray();
            if (character.Length != 1)
                throw new InvalidDataException("Encounter requires one character quest condition");
            string quest = character[0].StateKey;
            const string account = EncounterStateKeys.ReliquaryClaimed;
            if (
                !conditions.SetEquals(
                    new[] { ("account", account, "false"), ("character", quest, "false") }
                )
            )
                throw new InvalidDataException("Unsupported encounter availability conditions");
            var completions = Completions
                .Where(row => row.EncounterKey == encounter)
                .Select(row => (row.EventKind, row.StateScope, row.StateKey, row.ResultValue))
                .ToHashSet();
            if (
                !completions.SetEquals(
                    new[]
                    {
                        ("host_death", "account", account, "true"),
                        ("host_death", "character", quest, "true"),
                        ("scene_awake_quest_completed", "account", account, "true"),
                        ("scene_awake_account_claimed", "character", quest, "true"),
                    }
                )
            )
                throw new InvalidDataException("Unsupported or incomplete encounter effects");
            var eventConditions = EventConditions
                .Where(row => row.EncounterKey == encounter)
                .Select(row => (row.EventKind, row.StateScope, row.StateKey, row.RequiredValue))
                .ToHashSet();
            if (
                !eventConditions.SetEquals(
                    new[]
                    {
                        ("scene_awake_quest_completed", "character", quest, "true"),
                        ("scene_awake_account_claimed", "account", account, "true"),
                    }
                )
            )
                throw new InvalidDataException("Unsupported or incomplete encounter guards");
        }

        void ValidateState(EncounterRow row, string scope, string key, string value)
        {
            if (!roots.ContainsKey(row.EncounterKey))
                throw new InvalidDataException("Encounter state names unknown encounter");
            if (value is not ("true" or "false"))
                throw new InvalidDataException("Encounter state value must be true or false");
            if (scope == "account")
            {
                if (key != EncounterStateKeys.ReliquaryClaimed)
                    throw new InvalidDataException($"Unknown account state {key}");
            }
            else if (scope == "character")
            {
                if (!quests.Any(quest => quest.StableKey == key))
                    throw new InvalidDataException($"Unknown encounter character quest {key}");
            }
            else
                throw new InvalidDataException($"Unknown encounter state scope {scope}");
        }
    }

    private static void ValidateIdentity(EncounterRow row)
    {
        if (row == null || string.IsNullOrWhiteSpace(row.EncounterKey))
            throw new InvalidDataException("Invalid encounter identity");
    }

    private static void ValidateEvent(string kind)
    {
        if (
            kind
            is not ("host_death" or "scene_awake_quest_completed" or "scene_awake_account_claimed")
        )
            throw new InvalidDataException($"Unsupported encounter event {kind}");
    }
}

public static class EncounterStateKeys
{
    public const string ReliquaryClaimed = "account_state:reliquary_claimed";
    public const string ReturnZone = "character_state:reliquary_return_zone";
    public const string ReturnLanding = "character_state:reliquary_return_landing";
}

public abstract class EncounterRow
{
    [JsonProperty("encounter_key"), JsonRequired]
    public string EncounterKey { get; set; } = "";
}

public sealed class EncounterPlacement : EncounterRow
{
    [JsonProperty("context_kind"), JsonRequired]
    public string ContextKind { get; set; } = "";

    [JsonProperty("post_completion_role"), JsonRequired]
    public string PostCompletionRole { get; set; } = "";

    [JsonProperty("root_spawn_stable_key"), JsonRequired]
    public string RootSpawnStableKey { get; set; } = "";

    [JsonProperty("member_spawn_stable_key"), JsonRequired]
    public string MemberSpawnStableKey { get; set; } = "";

    [JsonProperty("role"), JsonRequired]
    public string Role { get; set; } = "";
}

public sealed class EncounterCondition : EncounterRow
{
    [JsonProperty("state_scope"), JsonRequired]
    public string StateScope { get; set; } = "";

    [JsonProperty("state_key"), JsonRequired]
    public string StateKey { get; set; } = "";

    [JsonProperty("required_value"), JsonRequired]
    public string RequiredValue { get; set; } = "";
}

public sealed class EncounterCompletion : EncounterRow
{
    [JsonProperty("event_kind"), JsonRequired]
    public string EventKind { get; set; } = "";

    [JsonProperty("state_scope"), JsonRequired]
    public string StateScope { get; set; } = "";

    [JsonProperty("state_key"), JsonRequired]
    public string StateKey { get; set; } = "";

    [JsonProperty("result_value"), JsonRequired]
    public string ResultValue { get; set; } = "";
}

public sealed class EncounterEventCondition : EncounterRow
{
    [JsonProperty("event_kind"), JsonRequired]
    public string EventKind { get; set; } = "";

    [JsonProperty("state_scope"), JsonRequired]
    public string StateScope { get; set; } = "";

    [JsonProperty("state_key"), JsonRequired]
    public string StateKey { get; set; } = "";

    [JsonProperty("required_value"), JsonRequired]
    public string RequiredValue { get; set; } = "";
}

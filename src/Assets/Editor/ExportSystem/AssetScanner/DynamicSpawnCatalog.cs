#nullable enable

using System;
using System.Collections.Generic;
using System.IO;

public enum DynamicSpawnClassification
{
    Unknown = 0,
    Allowed,
    Denied,
    Activation,
}

public struct CatalogEntry
{
    public DynamicSpawnClassification Classification { get; set; }
    public string? PositionField { get; set; }
    public string? PositionStrategy { get; set; }
    public bool IncludeHostPosition { get; set; }
    public string? TriggerItemField { get; set; }
    public string? TriggerMode { get; set; }
    public string? EventDisplayName { get; set; }
    public bool IncludeHostBounds { get; set; }
    public string? Reason { get; set; }
    public string? Rule { get; set; }

    // What the spawned character needs from others: "host", "checked_in", or a
    // controller field that names a SpawnPoint or a Character prefab.
    public IReadOnlyList<string> SummonedBy { get; set; }

    // "alive", "defeated", or "dialog". Set exactly when SummonedBy names someone.
    public string? Summon { get; set; }
}

public sealed class ActivationCatalogEntry
{
    public string Script { get; set; } = "";
    public string Rule { get; set; } = "";
    public IReadOnlyList<string> Fields { get; set; } = Array.Empty<string>();
}

public class DynamicSpawnCatalog
{
    private readonly Dictionary<(string script, string field), CatalogEntry> _entries = new();
    private readonly HashSet<string> _knownScripts = new();
    private readonly List<ActivationCatalogEntry> _activations = new();

    public IReadOnlyDictionary<(string script, string field), CatalogEntry> Entries => _entries;
    public IReadOnlyCollection<string> KnownScripts => _knownScripts;
    public IReadOnlyList<ActivationCatalogEntry> Activations => _activations;

    public static DynamicSpawnCatalog Load(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException("Dynamic spawn catalog is required", path);

        var catalog = new DynamicSpawnCatalog();
        string? section = null;
        var attributes = new Dictionary<string, string>();
        bool hasVersion = false;
        foreach (var rawLine in File.ReadAllLines(path))
        {
            var line = rawLine.Trim();
            if (line.Length == 0 || line.StartsWith("#", StringComparison.Ordinal))
                continue;
            if (line.StartsWith("[[", StringComparison.Ordinal))
            {
                if (section != null)
                    catalog.AddSection(section, attributes);
                section = line switch
                {
                    "[[allowed]]" => "allowed",
                    "[[denied]]" => "denied",
                    "[[activation]]" => "activation",
                    _ => throw new InvalidDataException($"Unknown catalog section: {line}"),
                };
                attributes = new Dictionary<string, string>();
                continue;
            }
            int equals = line.IndexOf('=');
            if (equals < 1)
                throw new InvalidDataException($"Invalid catalog line: {line}");
            var name = line.Substring(0, equals).Trim();
            var value = line.Substring(equals + 1).Trim();
            if (section == null)
            {
                if (name != "schema_version" || value != "1" || hasVersion)
                    throw new InvalidDataException($"Unknown catalog header: {line}");
                hasVersion = true;
            }
            else if (!attributes.TryAdd(name, value))
                throw new InvalidDataException($"Duplicate catalog attribute: {name}");
        }
        if (section != null)
            catalog.AddSection(section, attributes);
        if (!hasVersion)
            throw new InvalidDataException("Catalog schema_version is required");
        return catalog;
    }

    private void AddSection(string section, Dictionary<string, string> attributes)
    {
        foreach (var name in attributes.Keys)
        {
            bool valid = name == "script" || name == "fields";
            valid |= section == "activation" && name == "rule";
            valid |= section == "denied" && name == "reason";
            valid |=
                section == "allowed"
                && name
                    is "position_field"
                        or "position_strategy"
                        or "include_host_position"
                        or "trigger_item_field"
                        or "trigger_mode"
                        or "event_display_name"
                        or "include_host_bounds"
                        or "summoned_by"
                        or "summon"
                        or "reason";
            if (!valid)
                throw new InvalidDataException($"Unknown [[{section}]] catalog attribute: {name}");
        }
        string Required(string name) =>
            attributes.TryGetValue(name, out var value)
                ? value
                : throw new InvalidDataException($"[[{section}]] requires {name}");
        string? OptionalString(string name) =>
            attributes.TryGetValue(name, out var value) ? ParseString(value) : null;
        bool OptionalBool(string name)
        {
            if (!attributes.TryGetValue(name, out var value))
                return false;
            return value switch
            {
                "true" => true,
                "false" => false,
                _ => throw new InvalidDataException($"Invalid catalog boolean: {name} = {value}"),
            };
        }

        var script = ParseString(Required("script"));
        var fields = ParseFields(Required("fields"));
        var rule = section == "activation" ? ParseString(Required("rule")) : null;
        var classification = section switch
        {
            "allowed" => DynamicSpawnClassification.Allowed,
            "denied" => DynamicSpawnClassification.Denied,
            _ => DynamicSpawnClassification.Activation,
        };
        if (fields.Count == 0 && section != "activation")
            throw new InvalidDataException($"Empty [[{section}]] fields for {script}");
        IReadOnlyList<string> summonedBy = Array.Empty<string>();
        string? summon = null;
        if (section == "allowed")
        {
            // Every allowed field states who must be present or dead first, even when nobody must.
            summonedBy = ParseFields(Required("summoned_by"));
            summon = OptionalString("summon");
            if (summonedBy.Count == 0 && summon != null)
                throw new InvalidDataException($"{script} sets summon without summoned_by");
            if (summonedBy.Count > 0 && summon is not ("alive" or "defeated" or "dialog"))
                throw new InvalidDataException($"{script} needs summon alive, defeated, or dialog");
            if (summon == "dialog" && (summonedBy.Count != 1 || summonedBy[0] != "host"))
                throw new InvalidDataException(
                    $"{script} dialog summons are said to the host only"
                );
        }
        if (section == "activation")
        {
            foreach (var activation in _activations)
                if (activation.Script == script)
                    throw new InvalidDataException($"Duplicate activation script: {script}");
            _activations.Add(
                new ActivationCatalogEntry
                {
                    Script = script,
                    Rule = rule!,
                    Fields = fields,
                }
            );
        }
        _knownScripts.Add(script);
        foreach (var field in fields)
        {
            var entry = new CatalogEntry
            {
                Classification = classification,
                PositionField = OptionalString("position_field"),
                PositionStrategy = OptionalString("position_strategy"),
                IncludeHostPosition = OptionalBool("include_host_position"),
                TriggerItemField = OptionalString("trigger_item_field"),
                TriggerMode = OptionalString("trigger_mode"),
                EventDisplayName = OptionalString("event_display_name"),
                IncludeHostBounds = OptionalBool("include_host_bounds"),
                Reason = OptionalString("reason"),
                Rule = rule,
                SummonedBy = summonedBy,
                Summon = summon,
            };
            if (!_entries.TryAdd((script, field), entry))
                throw new InvalidOperationException($"Duplicate catalog entry: {script}.{field}");
        }
    }

    public CatalogEntry Classify(string scriptType, string fieldName) =>
        _entries.TryGetValue((scriptType, fieldName), out var entry) ? entry : default;

    public bool IsScriptKnown(string scriptType) => _knownScripts.Contains(scriptType);

    private static string ParseString(string value)
    {
        if (value.Length < 2 || value[0] != '"' || value[value.Length - 1] != '"')
            throw new InvalidDataException($"Expected quoted catalog string: {value}");
        var result = value.Substring(1, value.Length - 2);
        if (result.Length == 0 || result.Contains("\""))
            throw new InvalidDataException($"Invalid catalog string: {value}");
        return result;
    }

    private static List<string> ParseFields(string value)
    {
        if (value.Length < 2 || value[0] != '[' || value[value.Length - 1] != ']')
            throw new InvalidDataException($"Expected catalog fields array: {value}");
        var body = value.Substring(1, value.Length - 2).Trim();
        var result = new List<string>();
        if (body.Length == 0)
            return result;
        foreach (var part in body.Split(','))
        {
            var field = ParseString(part.Trim());
            if (result.Contains(field))
                throw new InvalidDataException($"Duplicate catalog field: {field}");
            result.Add(field);
        }
        return result;
    }
}

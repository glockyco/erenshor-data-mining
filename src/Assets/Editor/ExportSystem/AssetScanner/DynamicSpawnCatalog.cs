#nullable enable

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public enum DynamicSpawnClassification { Unknown = 0, Allowed, Denied }

public struct CatalogEntry
{
    public DynamicSpawnClassification Classification { get; set; }
    public string? PositionField { get; set; }   // comma-separated for multi-position spawns; listener splits
    public string? PositionStrategy { get; set; } // named resolver for non-Cartesian placement semantics
    public bool IncludeHostPosition { get; set; }
    public string? Reason { get; set; }
}

public class DynamicSpawnCatalog
{
    private readonly Dictionary<(string script, string field), CatalogEntry> _entries = new();
    private readonly HashSet<string> _knownScripts = new();

    public IReadOnlyDictionary<(string script, string field), CatalogEntry> Entries => _entries;
    public IReadOnlyCollection<string> KnownScripts => _knownScripts;

    public static DynamicSpawnCatalog Load(string path)
    {
        var catalog = new DynamicSpawnCatalog();
        if (!File.Exists(path))
        {
            Debug.LogError($"[DynamicSpawnCatalog] Catalog file not found: {path}");
            return catalog;
        }

        string? currentSection = null;
        string? currentScript = null;
        List<string>? currentFields = null;
        string? currentPositionField = null;
        string? currentPositionStrategy = null;
        bool currentIncludeHostPosition = false;
        string? currentReason = null;

        foreach (var rawLine in File.ReadAllLines(path))
        {
            var line = rawLine.Trim();
            if (line.StartsWith('#') || line.Length == 0) continue;

            if (line == "[[allowed]]" || line == "[[denied]]")
            {
                if (currentScript != null && currentFields != null)
                    catalog.AddSection(currentSection!, currentScript, currentFields, currentPositionField, currentPositionStrategy, currentIncludeHostPosition, currentReason);
                currentSection = line == "[[allowed]]" ? "allowed" : "denied";
                currentScript = null; currentFields = null; currentPositionField = null; currentPositionStrategy = null; currentIncludeHostPosition = false; currentReason = null;
            }
            else if (line.StartsWith("script = "))
            {
                currentScript = ParseStringValue(line);
            }
            else if (line.StartsWith("fields = "))
            {
                currentFields = ParseStringArrayValue(line);
            }
            else if (line.StartsWith("position_field = "))
            {
                currentPositionField = ParseStringValue(line);
            }
            else if (line.StartsWith("position_strategy = "))
            {
                currentPositionStrategy = ParseStringValue(line);
            }
            else if (line.StartsWith("include_host_position = "))
            {
                currentIncludeHostPosition = ParseBoolValue(line);
            }
            else if (line.StartsWith("reason = "))
            {
                currentReason = ParseStringValue(line);
            }
        }
        if (currentScript != null && currentFields != null)
            catalog.AddSection(currentSection!, currentScript, currentFields, currentPositionField, currentPositionStrategy, currentIncludeHostPosition, currentReason);

        return catalog;
    }

    private void AddSection(string section, string script, List<string> fields, string? positionField, string? positionStrategy, bool includeHostPosition, string? reason)
    {
        var classification = section == "allowed" ? DynamicSpawnClassification.Allowed : DynamicSpawnClassification.Denied;
        _knownScripts.Add(script);
        foreach (var field in fields)
        {
            var key = (script, field);
            if (_entries.ContainsKey(key))
            {
                throw new InvalidOperationException(
                    $"Duplicate catalog entry: {script}.{field} appears in multiple [[allowed]]/[[denied]] sections. " +
                    "Each (script, field) pair must be classified exactly once.");
            }
            _entries[key] = new CatalogEntry
            {
                Classification = classification,
                PositionField = positionField,
                PositionStrategy = positionStrategy,
                IncludeHostPosition = includeHostPosition,
                Reason = reason,
            };
        }
    }

    public CatalogEntry Classify(string scriptType, string fieldName)
    {
        return _entries.TryGetValue((scriptType, fieldName), out var entry) ? entry : default;
    }

    public bool IsScriptKnown(string scriptType) => _knownScripts.Contains(scriptType);

    private static string ParseStringValue(string line)
    {
        // script = "Chessboard"  →  Chessboard
        var eq = line.IndexOf('=');
        if (eq < 0) return string.Empty;
        var val = line.Substring(eq + 1).Trim();
        if (val.StartsWith('"') && val.EndsWith('"'))
            val = val.Substring(1, val.Length - 2);
        return val;
    }

    private static bool ParseBoolValue(string line)
    {
        var eq = line.IndexOf('=');
        return eq >= 0 && line.Substring(eq + 1).Trim().Equals("true", StringComparison.OrdinalIgnoreCase);
    }

    private static List<string> ParseStringArrayValue(string line)
    {
        var eq = line.IndexOf('=');
        if (eq < 0) return new List<string>();
        var val = line.Substring(eq + 1).Trim();
        // Strip outer brackets
        if (val.StartsWith('[') && val.EndsWith(']'))
            val = val.Substring(1, val.Length - 2);
        var result = new List<string>();
        foreach (var part in val.Split(','))
        {
            var s = part.Trim();
            if (s.StartsWith('"') && s.EndsWith('"'))
                s = s.Substring(1, s.Length - 2);
            if (s.Length > 0)
                result.Add(s);
        }
        return result;
    }
}

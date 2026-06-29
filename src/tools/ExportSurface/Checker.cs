using Mono.Cecil;

namespace ExportSurface;

internal sealed record Finding(string Type, string Field, string Kind, string? Expected, string? Actual);

/// <summary>
/// Metadata-only field enumeration and diff against the manifest.
/// Implements invariants 1–2 (spec §5): completeness, no staleness/retype.
/// </summary>
internal static class Checker
{
    /// <summary>
    /// Enumerate public instance fields of a type via Mono.Cecil metadata.
    /// Never executes code — metadata read only (spec §6).
    /// </summary>
    public static Dictionary<string, string> PublicInstanceFields(ModuleDefinition module, string typeFullName)
    {
        var type = module.GetType(typeFullName)
            ?? throw new InvalidDataException($"in-scope type not found in assembly: {typeFullName}");
        var fields = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var f in type.Fields)
        {
            if (!f.IsPublic || f.IsStatic) continue;   // public instance only (spec §1)
            fields[f.Name] = f.FieldType.FullName;
        }
        return fields;
    }

    /// <summary>
    /// Diff actual fields against manifest entries.
    /// Findings: unclassified (in code but absent/unclassified in manifest),
    /// retype (type mismatch), stale (in manifest but absent from code).
    /// </summary>
    public static IEnumerable<Finding> Diff(
        string typeName,
        Dictionary<string, FieldEntry> manifestFields,
        Dictionary<string, string> actualFields)
    {
        foreach (var (name, actualType) in actualFields)
        {
            if (!manifestFields.TryGetValue(name, out var entry))
            {
                // Invariant 1: field exists in code but is absent from the manifest.
                yield return new Finding(typeName, name, "unclassified", null, actualType);
            }
            else if (!IsClassified(entry))
            {
                // Invariant 1: field is in the manifest but not fully classified.
                // A valid classification requires both a status and its
                // required annotation: captured -> by, ignored -> reason
                // (spec §4). Seeded entries have empty status; a half-classified
                // entry (captured with no by, ignored with no reason) is treated
                // identically -- both mean "classify this field."
                yield return new Finding(typeName, name, "unclassified", null, actualType);
            }
            else if (entry.Type != actualType)
            {
                // Invariant 2: type drift.
                yield return new Finding(typeName, name, "retype", entry.Type, actualType);
            }
        }

        foreach (var (name, entry) in manifestFields)
        {
            // Invariant 2: manifest references a field that no longer exists.
            if (!actualFields.ContainsKey(name))
                yield return new Finding(typeName, name, "stale", entry.Type, null);
        }
    }
    /// <summary>
    /// A manifest entry is fully classified when its status is valid and its
    /// required annotation is present: captured -> by, ignored -> reason (spec §4).
    /// </summary>
    private static bool IsClassified(FieldEntry entry) => entry.Status switch
    {
        "captured" => !string.IsNullOrWhiteSpace(entry.By),
        "ignored" => !string.IsNullOrWhiteSpace(entry.Reason),
        _ => false,
    };
}

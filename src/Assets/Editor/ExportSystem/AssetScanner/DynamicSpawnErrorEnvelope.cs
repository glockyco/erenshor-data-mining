#nullable enable

using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

public class DynamicSpawnErrorEnvelope
{
    public List<Finding> Findings { get; } = new();
    public List<StaleEntry> StaleEntries { get; } = new();

    public bool HasErrors => Findings.Count > 0 || StaleEntries.Count > 0;

    public struct Finding
    {
        public string ScriptType;
        public string FieldName;
        public string FieldKind;
        public string? ExamplePrefabPath;
        public string? ExampleStableKey;
        public string? ExampleDisplayName;
        public string? HostScenePath;
    }

    public struct StaleEntry
    {
        public string Kind;        // "allowed" | "denied"
        public string ScriptType;
        public string FieldName;
    }

    public void WriteToFile(string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var sb = new StringBuilder();
        sb.AppendLine("{");
        sb.AppendLine("  \"type\": \"erenshor://export/unclassified-spawn-candidates\",");
        sb.AppendLine("  \"title\": \"Dynamic spawn candidates not classified in catalog\",");
        sb.AppendLine("  \"status\": 3,");
        sb.AppendLine($"  \"detail\": \"Export found {Findings.Count} unclassified and {StaleEntries.Count} stale entries.\",");
        sb.AppendLine("  \"findings\": [");
        for (int i = 0; i < Findings.Count; i++)
        {
            var f = Findings[i];
            sb.AppendLine("    {");
            sb.AppendLine($"      \"script_type\": \"{Escape(f.ScriptType)}\",");
            sb.AppendLine($"      \"field_name\": \"{Escape(f.FieldName)}\",");
            sb.AppendLine($"      \"field_kind\": \"{Escape(f.FieldKind)}\"");
            if (f.ExamplePrefabPath != null) sb.AppendLine($"      ,\"example_prefab_path\": \"{Escape(f.ExamplePrefabPath)}\"");
            if (f.ExampleStableKey != null) sb.AppendLine($"      ,\"example_stable_key\": \"{Escape(f.ExampleStableKey)}\"");
            if (f.ExampleDisplayName != null) sb.AppendLine($"      ,\"example_display_name\": \"{Escape(f.ExampleDisplayName)}\"");
            if (f.HostScenePath != null) sb.AppendLine($"      ,\"host_scene_path\": \"{Escape(f.HostScenePath)}\"");
            sb.Append("    }");
            if (i < Findings.Count - 1) sb.AppendLine(",");
            else sb.AppendLine();
        }
        sb.AppendLine("  ],");
        sb.AppendLine("  \"stale_entries\": [");
        for (int i = 0; i < StaleEntries.Count; i++)
        {
            var s = StaleEntries[i];
            sb.AppendLine("    {");
            sb.AppendLine($"      \"kind\": \"{Escape(s.Kind)}\",");
            sb.AppendLine($"      \"script_type\": \"{Escape(s.ScriptType)}\",");
            sb.AppendLine($"      \"field_name\": \"{Escape(s.FieldName)}\"");
            sb.Append("    }");
            if (i < StaleEntries.Count - 1) sb.AppendLine(",");
            else sb.AppendLine();
        }
        sb.AppendLine("  ]");
        sb.AppendLine("}");
        File.WriteAllText(path, sb.ToString());
    }

    public void PrintHumanSummary()
    {
        if (!HasErrors) return;
        Debug.LogError("[DYNAMIC_SPAWN_GATE] Dynamic spawn coverage gate failed.");
        Debug.LogError($"  {Findings.Count} unclassified candidates, {StaleEntries.Count} stale catalog entries.");
        foreach (var f in Findings)
            Debug.LogError($"  • {f.ScriptType}.{f.FieldName}  (example: {f.ExampleDisplayName ?? f.ExampleStableKey ?? "unknown"})");
        foreach (var s in StaleEntries)
            Debug.LogError($"  stale: {s.Kind} {s.ScriptType}.{s.FieldName} (script not found in Assembly-CSharp)");
    }

    private static string Escape(string s) => s.Replace("\\", "\\\\").Replace("\"", "\\\"");
}

using System.Text.Json;
using ExportSurface;
using Mono.Cecil;

// --- arg parsing (mirrors CodeFacts/Program.cs shape) ---

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: ExportSurface <assembly.dll> <manifest.json> [--out <result.json>]");
    return 2;
}

string assemblyPath = Path.GetFullPath(args[0]);
string manifestPath = Path.GetFullPath(args[1]);
string? outPath = null;
for (int i = 2; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--out":
            if (++i >= args.Length)
            {
                Console.Error.WriteLine("--out requires a value");
                return 2;
            }
            outPath = Path.GetFullPath(args[i]);
            break;
        default:
            Console.Error.WriteLine($"unknown argument: {args[i]}");
            return 2;
    }
}

// --- validation ---

if (!File.Exists(assemblyPath))
{
    Console.Error.WriteLine($"assembly not found: {assemblyPath}");
    return 2;
}
// Only the shipped binary is authoritative (spec §6).
if (!assemblyPath.Replace('\\', '/').Contains("/Managed/"))
{
    Console.Error.WriteLine($"refusing non-shipped assembly path (must be under .../Managed/): {assemblyPath}");
    return 2;
}
if (!File.Exists(manifestPath))
{
    Console.Error.WriteLine($"manifest not found: {manifestPath}");
    return 2;
}

// --- run the check ---

var manifest = Manifest.Load(manifestPath);
var findings = new List<Finding>();
using (var asm = AssemblyDefinition.ReadAssembly(assemblyPath))
{
    var module = asm.MainModule;
    foreach (var typeName in manifest.Types)
    {
        var actual = Checker.PublicInstanceFields(module, typeName);
        var declared = manifest.Fields.TryGetValue(typeName, out var d) ? d : new();
        findings.AddRange(Checker.Diff(typeName, declared, actual));
    }
}

// --- emit the envelope ---

var envelope = new
{
    type = "erenshor://export/field-coverage-drift",
    status = findings.Count == 0 ? 0 : 1,
    detail = $"{findings.Count} field-coverage finding(s) against {Path.GetFileName(manifestPath)}.",
    findings = findings
        .OrderBy(f => f.Type)
        .ThenBy(f => f.Field)
        .Select(f => new
        {
            script_type = f.Type,
            field_name = f.Field,
            kind = f.Kind,
            expected = f.Expected,
            actual = f.Actual,
        }),
};
string json = JsonSerializer.Serialize(envelope, new JsonSerializerOptions { WriteIndented = true });
if (outPath is null) Console.WriteLine(json);
else File.WriteAllText(outPath, json);
return findings.Count == 0 ? 0 : 1;

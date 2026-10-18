using System.Text.Json;
using CodeFacts;
using ICSharpCode.Decompiler;
using ICSharpCode.Decompiler.CSharp;
using ICSharpCode.Decompiler.Metadata;

if (args.Length < 2)
{
    Console.Error.WriteLine(
        "usage: CodeFacts <assembly.dll> <specs.json> [--variant <name>] [--out <result.json>] [--inventory]"
    );
    return 2;
}

string assemblyPath = Path.GetFullPath(args[0]);
string specsPath = Path.GetFullPath(args[1]);
string? variant = null;
string? outPath = null;
bool inventoryOnly = false;
for (int i = 2; i < args.Length; i++)
{
    switch (args[i])
    {
        case "--inventory":
            inventoryOnly = true;
            break;
        case "--variant":
            if (++i >= args.Length)
            {
                Console.Error.WriteLine("--variant requires a value");
                return 2;
            }
            variant = args[i];
            break;
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

if (!File.Exists(assemblyPath))
{
    Console.Error.WriteLine($"assembly not found: {assemblyPath}");
    return 2;
}

// Only the shipped binary is authoritative.
if (!assemblyPath.Replace('\\', '/').Contains("/Managed/"))
{
    Console.Error.WriteLine(
        $"refusing non-shipped assembly path (must be under .../Managed/): {assemblyPath}"
    );
    return 2;
}
if (!File.Exists(specsPath))
{
    Console.Error.WriteLine($"specs not found: {specsPath}");
    return 2;
}

var resolver = new UniversalAssemblyResolver(
    assemblyPath,
    throwOnError: false,
    targetFramework: null
);
var decompiler = new CSharpDecompiler(assemblyPath, resolver, new DecompilerSettings());
var inventory = BehaviourCoverage.Inventory(decompiler);
if (inventoryOnly)
{
    string inventoryJson = JsonSerializer.Serialize(
        inventory,
        new JsonSerializerOptions { WriteIndented = true }
    );
    if (outPath is null)
        Console.WriteLine(inventoryJson);
    else
        File.WriteAllText(outPath, inventoryJson);
    return 0;
}
var result = Runner.Run(assemblyPath, specsPath, variant);
try
{
    var catalog = BehaviourCoverage.Load(
        Path.Combine(Path.GetDirectoryName(specsPath)!, "behaviour-coverage.json")
    );
    result.Errors.AddRange(
        BehaviourCoverage.Check(
            inventory,
            catalog,
            decompiler
                .TypeSystem.MainModule.TypeDefinitions.Select(t => t.FullName)
                .ToHashSet(StringComparer.Ordinal)
        )
    );
}
catch (Exception ex)
{
    result.Errors.Add($"behaviour coverage: {ex.Message}");
}
string json = result.ToJson();
if (outPath is null)
    Console.WriteLine(json);
else
    File.WriteAllText(outPath, json);
return result.Ok ? 0 : 1;

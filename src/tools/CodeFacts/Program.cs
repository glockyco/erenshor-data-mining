using CodeFacts;

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: CodeFacts <assembly.dll> <specs.json> [--out <result.json>]");
    return 2;
}

string assemblyPath = Path.GetFullPath(args[0]);
string specsPath = Path.GetFullPath(args[1]);
string? outPath = args.Length >= 4 && args[2] == "--out" ? Path.GetFullPath(args[3]) : null;

if (!File.Exists(assemblyPath))
{
    Console.Error.WriteLine($"assembly not found: {assemblyPath}");
    return 2;
}
// Only the shipped binary is authoritative.
if (!assemblyPath.Replace('\\', '/').Contains("/Managed/"))
{
    Console.Error.WriteLine($"refusing non-shipped assembly path (must be under .../Managed/): {assemblyPath}");
    return 2;
}
if (!File.Exists(specsPath))
{
    Console.Error.WriteLine($"specs not found: {specsPath}");
    return 2;
}

var result = Runner.Run(assemblyPath, specsPath); // implemented in Task 2
string json = result.ToJson();
if (outPath is null) Console.WriteLine(json);
else File.WriteAllText(outPath, json);
return result.Ok ? 0 : 1;

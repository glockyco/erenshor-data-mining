namespace CodeFacts;

// Temporary stub. Task 2 replaces the internals with the real spec model,
// decompiler-backed extraction, and JSON serialization.
internal static class Runner
{
    public static RunResult Run(string assemblyPath, string specsPath) =>
        throw new NotImplementedException();
}

internal sealed class RunResult
{
    public bool Ok { get; init; }

    public string ToJson() => throw new NotImplementedException();
}

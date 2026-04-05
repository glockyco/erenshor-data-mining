namespace AdventureGuide.Diagnostics;

/// <summary>
/// Lightweight diagnostics sink for logic layers that must stay loadable in pure
/// test projects.
///
/// The composition root wires these delegates to BepInEx logging at runtime.
/// Tests can leave them unset.
/// </summary>
internal static class GuideDiagnostics
{
    internal static System.Action<string>? LogInfo { get; set; }
    internal static System.Action<string>? LogWarning { get; set; }
    internal static System.Action<string>? LogError { get; set; }
}

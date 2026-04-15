using System.Text;
using AdventureGuide.Resolution;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Builds a human-readable multi-line trace of the resolution pipeline.
/// Used by <see cref="DebugAPI.TraceQuest"/> for HotRepl diagnostics.
/// </summary>
public sealed class TextResolutionTracer : IResolutionTracer
{
    private readonly StringBuilder _sb = new();

    public string GetTrace() => _sb.ToString();

    public void OnResolveBegin(string nodeKey)
    {
        _sb.AppendLine($"TraceQuest(\"{nodeKey}\")");
    }

    public void OnResolveEnd(int targetCount)
    {
        _sb.AppendLine($"  Total targets: {targetCount}");
    }

    public void OnQuestPhase(int questIndex, string? dbName, string phase)
    {
        _sb.AppendLine($"  Phase: {phase} (questIndex={questIndex}, db={dbName ?? "?"})");
    }

    public void OnFrontierEntry(int questIndex, string? questDbName, string phase, int requiredForQuestIndex)
    {
        string reqFor = requiredForQuestIndex >= 0 ? $", requiredFor={requiredForQuestIndex}" : "";
        _sb.AppendLine($"    Frontier: questIndex={questIndex}, db={questDbName ?? "?"}, phase={phase}{reqFor}");
    }

    public void OnTargetMaterialized(int targetNodeId, int positionNodeId, string role, string? scene, bool isActionable)
    {
        string actionable = isActionable ? "actionable" : "non-actionable";
        _sb.AppendLine($"    Target: node={targetNodeId}, pos={positionNodeId}, role={role}, scene={scene ?? "?"}, {actionable}");
    }

    public void OnHostileDropFilter(int itemIndex, int totalSources, int suppressedCount)
    {
        _sb.AppendLine($"    HostileDropFilter: itemIndex={itemIndex}, total={totalSources}, suppressed={suppressedCount}");
    }

    public void OnUnlockEvaluation(int targetNodeId, bool isUnlocked)
    {
        _sb.AppendLine($"    Unlock: node={targetNodeId}, unlocked={isUnlocked}");
    }
}

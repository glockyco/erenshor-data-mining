namespace AdventureGuide.Resolution;

/// <summary>
/// Optional observer threaded through the resolution pipeline.
/// Normal operation passes null; all call sites use <c>tracer?.OnXxx(...)</c>
/// so there is zero overhead when inactive.
/// </summary>
public interface IResolutionTracer
{
    void OnQuestPhase(int questIndex, string? dbName, string phase);
    void OnFrontierEntry(
        int questIndex,
        string? questDbName,
        string phase,
        int requiredForQuestIndex
    );
    void OnTargetMaterialized(
        int targetNodeId,
        int positionNodeId,
        string role,
        string? scene,
        bool isActionable
    );
    void OnHostileDropFilter(int itemIndex, int totalSources, int suppressedCount);
    void OnUnlockEvaluation(int targetNodeId, bool isUnlocked);
    void OnResolveBegin(string nodeKey);
    void OnResolveEnd(int targetCount);
}

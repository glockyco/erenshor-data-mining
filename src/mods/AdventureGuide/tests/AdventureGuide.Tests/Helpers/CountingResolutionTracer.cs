using AdventureGuide.Resolution;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Tracer that counts frontier-entry visits during resolution. Memoized
/// resolution visits each quest's frontier at most once per session, so the
/// count is bounded by total quest count. Combinatorial blow-up in
/// shared-reward subtrees would inflate it exponentially.
/// </summary>
internal sealed class CountingResolutionTracer : IResolutionTracer
{
	public int FrontierEntryCount { get; private set; }

	public void OnQuestPhase(int questIndex, string? dbName, string phase) { }

	public void OnFrontierEntry(
		int questIndex,
		string? questDbName,
		string phase,
		int requiredForQuestIndex
	)
	{
		FrontierEntryCount++;
	}

	public void OnTargetMaterialized(
		int targetNodeId,
		int positionNodeId,
		string role,
		string? scene,
		bool isActionable
	) { }

	public void OnHostileDropFilter(int itemIndex, int totalSources, int suppressedCount) { }

	public void OnUnlockEvaluation(int targetNodeId, bool isUnlocked) { }

	public void OnResolveBegin(string nodeKey) { }

	public void OnResolveEnd(int targetCount) { }
}

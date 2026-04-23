using AdventureGuide.Frontier;

namespace AdventureGuide.Resolution;

public sealed class QuestResolutionRecord
{
	private readonly Func<IReadOnlyList<ResolvedQuestTarget>> _navigationTargetsFactory;
	private IReadOnlyList<ResolvedQuestTarget>? _navigationTargets;

	public QuestResolutionRecord(
		string questKey,
		string currentScene,
		IReadOnlyList<FrontierEntry> frontier,
		IReadOnlyList<ResolvedTarget> compiledTargets,
		Func<IReadOnlyList<ResolvedQuestTarget>> navigationTargetsFactory,
		IReadOnlyDictionary<string, int> blockingZoneLineByScene)
	{
		QuestKey = questKey;
		CurrentScene = currentScene ?? string.Empty;
		Frontier = frontier;
		CompiledTargets = compiledTargets;
		_navigationTargetsFactory = navigationTargetsFactory;
		BlockingZoneLineByTargetScene = blockingZoneLineByScene;
	}

	public string QuestKey { get; }
	public string CurrentScene { get; }
	public IReadOnlyList<FrontierEntry> Frontier { get; }
	public IReadOnlyList<ResolvedTarget> CompiledTargets { get; }
	public IReadOnlyDictionary<string, int> BlockingZoneLineByTargetScene { get; }
	public IReadOnlyList<ResolvedQuestTarget> NavigationTargets =>
		_navigationTargets ??= _navigationTargetsFactory();

	public bool TryGetBlockingZoneLineNodeId(string? targetScene, out int zoneLineNodeId)
	{
		zoneLineNodeId = default;
		if (string.IsNullOrWhiteSpace(targetScene))
			return false;
		return BlockingZoneLineByTargetScene.TryGetValue(targetScene, out zoneLineNodeId);
	}
}

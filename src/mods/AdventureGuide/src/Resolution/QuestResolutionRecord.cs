using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

public sealed class QuestResolutionRecord
{
	private readonly Func<IReadOnlyList<ResolvedQuestTarget>> _navigationTargetsFactory;
	private IReadOnlyList<ResolvedQuestTarget>? _navigationTargets;
	private readonly IReadOnlyDictionary<string, int> _blockingZoneLineByScene;

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
		_blockingZoneLineByScene = blockingZoneLineByScene;
	}

	public string QuestKey { get; }
	public string CurrentScene { get; }
	public IReadOnlyList<FrontierEntry> Frontier { get; }
	public IReadOnlyList<ResolvedTarget> CompiledTargets { get; }
	public IReadOnlyList<ResolvedQuestTarget> NavigationTargets =>
		_navigationTargets ??= _navigationTargetsFactory();

	public bool TryGetBlockingZoneLineNodeId(string? targetScene, out int zoneLineNodeId)
	{
		zoneLineNodeId = default;
		if (string.IsNullOrWhiteSpace(targetScene))
			return false;
		return _blockingZoneLineByScene.TryGetValue(targetScene, out zoneLineNodeId);
	}
}

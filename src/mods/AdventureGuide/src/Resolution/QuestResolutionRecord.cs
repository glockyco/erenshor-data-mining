using AdventureGuide.Frontier;

namespace AdventureGuide.Resolution;

public sealed class QuestResolutionRecord
{
	private readonly Func<IReadOnlyList<ResolvedQuestTarget>> _navigationTargetsFactory;
	private readonly Func<QuestDetailState> _detailStateFactory;
	private IReadOnlyList<ResolvedQuestTarget>? _navigationTargets;

	public QuestResolutionRecord(
		string questKey,
		string currentScene,
		IReadOnlyList<FrontierEntry> frontier,
		IReadOnlyList<ResolvedTarget> compiledTargets,
		Func<IReadOnlyList<ResolvedQuestTarget>> navigationTargetsFactory,
		IReadOnlyDictionary<string, int> blockingZoneLineByScene,
		Func<QuestDetailState> detailStateFactory)
	{
		QuestKey = questKey;
		CurrentScene = currentScene ?? string.Empty;
		Frontier = frontier;
		CompiledTargets = compiledTargets;
		_navigationTargetsFactory = navigationTargetsFactory;
		BlockingZoneLineByTargetScene = blockingZoneLineByScene;
		_detailStateFactory = detailStateFactory;
	}

	public string QuestKey { get; }
	public string CurrentScene { get; }
	public IReadOnlyList<FrontierEntry> Frontier { get; }
	public IReadOnlyList<ResolvedTarget> CompiledTargets { get; }
	public IReadOnlyDictionary<string, int> BlockingZoneLineByTargetScene { get; }
	public IReadOnlyList<ResolvedQuestTarget> NavigationTargets =>
		_navigationTargets ??= _navigationTargetsFactory();

	public QuestDetailState DetailState => _detailStateFactory();

	internal bool HasSameDetailProjectionState(
		QuestResolutionRecord other,
		QuestDetailState detailState,
		QuestDetailState otherDetailState)
	{
		return string.Equals(QuestKey, other.QuestKey, StringComparison.Ordinal)
            && BlockingZoneMapsEqual(BlockingZoneLineByTargetScene, other.BlockingZoneLineByTargetScene)
            && (ReferenceEquals(detailState, otherDetailState) || detailState.HasSameSnapshot(otherDetailState));
	}

	public bool TryGetBlockingZoneLineNodeId(string? targetScene, out int zoneLineNodeId)
	{
		zoneLineNodeId = default;
		if (string.IsNullOrWhiteSpace(targetScene))
			return false;
		return BlockingZoneLineByTargetScene.TryGetValue(targetScene, out zoneLineNodeId);
	}

	private static bool BlockingZoneMapsEqual(
		IReadOnlyDictionary<string, int> left,
		IReadOnlyDictionary<string, int> right)
	{
		if (left.Count != right.Count)
			return false;

		foreach (var entry in left)
		{
			if (!right.TryGetValue(entry.Key, out int rightValue) || rightValue != entry.Value)
				return false;
		}

		return true;
	}
}

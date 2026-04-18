using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Canonical maintained-view record for one quest in one scene. Shared across
/// navigation, tracker, markers, and detail projection.
///
/// NavigationTargets is computed on first access. Consumers that only need
/// CompiledTargets (markers, tracker summary) avoid the projection cost
/// entirely; consumers that need it (navigation, UI tree) pay once and the
/// result is memoized on the record.
/// </summary>
public sealed class QuestResolutionRecord
{
	private readonly QuestPhase[] _questPhases;
	private readonly int[] _itemCounts;
	private readonly IReadOnlyDictionary<string, int> _blockingZoneLineByScene;
	private readonly Func<IReadOnlyList<ResolvedQuestTarget>> _navigationTargetsFactory;
	private IReadOnlyList<ResolvedQuestTarget>? _navigationTargets;

	public QuestResolutionRecord(
		string questKey,
		string currentScene,
		int questIndex,
		IReadOnlyList<FrontierEntry> frontier,
		IReadOnlyList<ResolvedTarget> compiledTargets,
		Func<IReadOnlyList<ResolvedQuestTarget>> navigationTargetsFactory,
		IReadOnlyList<QuestPhase> questPhases,
		IReadOnlyList<int> itemCounts,
		IReadOnlyDictionary<string, int> blockingZoneLineByScene
	)
	{
		QuestKey = questKey;
		CurrentScene = currentScene ?? string.Empty;
		QuestIndex = questIndex;
		Frontier = frontier;
		CompiledTargets = compiledTargets;
		_navigationTargetsFactory = navigationTargetsFactory;
		_questPhases = questPhases.ToArray();
		_itemCounts = itemCounts.ToArray();
		_blockingZoneLineByScene = blockingZoneLineByScene;
	}

	public string QuestKey { get; }

	public string CurrentScene { get; }

	public int QuestIndex { get; }

	public IReadOnlyList<FrontierEntry> Frontier { get; }

	public IReadOnlyList<ResolvedTarget> CompiledTargets { get; }

	/// <summary>
	/// Pure projection of <see cref="CompiledTargets"/>. Computed on first
	/// access and memoized. Consumers that don't read this property never pay
	/// the projection cost.
	/// </summary>
	public IReadOnlyList<ResolvedQuestTarget> NavigationTargets =>
		_navigationTargets ??= _navigationTargetsFactory();

	public QuestPhase GetQuestPhase(int questIndex) =>
		questIndex >= 0 && questIndex < _questPhases.Length
			? _questPhases[questIndex]
			: QuestPhase.NotReady;

	public bool IsQuestCompleted(int questIndex) => GetQuestPhase(questIndex) == QuestPhase.Completed;

	public int GetItemCount(int itemIndex) =>
		itemIndex >= 0 && itemIndex < _itemCounts.Length ? _itemCounts[itemIndex] : 0;

	public bool TryGetBlockingZoneLineNodeId(string? targetScene, out int zoneLineNodeId)
	{
		zoneLineNodeId = default;
		if (string.IsNullOrWhiteSpace(targetScene))
			return false;

		return _blockingZoneLineByScene.TryGetValue(targetScene, out zoneLineNodeId);
	}
}

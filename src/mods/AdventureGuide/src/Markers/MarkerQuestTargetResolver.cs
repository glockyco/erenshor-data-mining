using AdventureGuide.Resolution;

namespace AdventureGuide.Markers;

/// <summary>
/// Resolves compiled active-marker targets for quests.
/// </summary>
public sealed class MarkerQuestTargetResolver
{
	private readonly CompiledGuide.CompiledGuide _guide;
	private readonly QuestResolutionService _questResolutionService;

	public MarkerQuestTargetResolver(
		CompiledGuide.CompiledGuide guide,
		QuestResolutionService questResolutionService
	)
	{
		_guide = guide;
		_questResolutionService = questResolutionService;
	}

	public IReadOnlyList<ResolvedTarget> Resolve(string questDbName, string currentScene) =>
		Resolve(questDbName, currentScene, session: null);

	internal IReadOnlyList<ResolvedTarget> Resolve(
		string questDbName,
		string currentScene,
		SourceResolver.ResolutionSession? session
	)
	{
		int questIndex =
			FindQuestIndexByDbName(questDbName)
			?? throw new InvalidOperationException(
				$"Compiled guide does not contain quest DB name '{questDbName}'."
			);
		string questKey = _guide.GetNodeKey(_guide.QuestNodeId(questIndex));
		return _questResolutionService.ResolveQuest(questKey, currentScene, session).CompiledTargets;
	}

	internal IReadOnlyDictionary<string, IReadOnlyList<ResolvedTarget>> ResolveQuestKeys(
		IEnumerable<string> questKeys,
		string currentScene,
		SourceResolver.ResolutionSession? session
	)
	{
		var records = _questResolutionService.ResolveBatch(questKeys, currentScene, session);
		var results = new Dictionary<string, IReadOnlyList<ResolvedTarget>>(StringComparer.Ordinal);
		foreach (var entry in records)
			results[entry.Key] = entry.Value.CompiledTargets;
		return results;
	}

	private int? FindQuestIndexByDbName(string questDbName)
	{
		for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
		{
			int nodeId = _guide.QuestNodeId(questIndex);
			string? nodeDbName = _guide.GetDbName(nodeId);
			if (nodeDbName == null)
				continue;
			if (string.Equals(nodeDbName, questDbName, StringComparison.OrdinalIgnoreCase))
				return questIndex;
		}

		return null;
	}
}

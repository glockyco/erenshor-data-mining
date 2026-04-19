using AdventureGuide.Resolution;
using AdventureGuide.State;

namespace AdventureGuide.Markers;

/// <summary>
/// Resolves compiled active-marker targets for quests.
/// </summary>
public sealed class MarkerQuestTargetResolver
{
	private readonly CompiledGuide.CompiledGuide _guide;
	private readonly GuideReader _reader;

	public MarkerQuestTargetResolver(
		CompiledGuide.CompiledGuide guide,
		GuideReader reader)
	{
		_guide = guide;
		_reader = reader;
	}

	public IReadOnlyList<ResolvedTarget> Resolve(string questDbName, string currentScene) =>
		Resolve(questDbName, currentScene, session: null);

	internal IReadOnlyList<ResolvedTarget> Resolve(
		string questDbName,
		string currentScene,
		SourceResolver.ResolutionSession? session)
	{
		int questIndex =
			FindQuestIndexByDbName(questDbName)
			?? throw new InvalidOperationException(
				$"Compiled guide does not contain quest DB name '{questDbName}'.");
		string questKey = _guide.GetNodeKey(_guide.QuestNodeId(questIndex));
		_ = session;
		return _reader.ReadQuestResolution(questKey, currentScene).CompiledTargets;
	}

	internal IReadOnlyDictionary<string, IReadOnlyList<ResolvedTarget>> ResolveQuestKeys(
		IEnumerable<string> questKeys,
		string currentScene,
		SourceResolver.ResolutionSession? session)
	{
		_ = session;
		var results = new Dictionary<string, IReadOnlyList<ResolvedTarget>>(StringComparer.Ordinal);
		foreach (var questKey in questKeys)
			results[questKey] = _reader.ReadQuestResolution(questKey, currentScene).CompiledTargets;
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

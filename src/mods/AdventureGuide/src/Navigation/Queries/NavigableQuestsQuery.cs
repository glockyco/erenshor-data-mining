using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Navigation.Queries;

public sealed class NavigableQuestsQuery
{
	private readonly CompiledGuideModel _guide;
	private readonly GuideReader _reader;

	public Query<Unit, NavigableQuestSet> Query { get; }

	public NavigableQuestsQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		GuideReader reader)
	{
		_guide = guide;
		_reader = reader;
		Query = engine.DefineQuery<Unit, NavigableQuestSet>(
			name: "NavigableQuests",
			compute: Compute);
	}

	private NavigableQuestSet Compute(ReadContext<FactKey> ctx, Unit _)
	{
		var keys = new HashSet<string>(StringComparer.Ordinal);

		foreach (var dbName in _reader.ReadActionableQuestDbNames())
		{
			_reader.ReadQuestActive(dbName);
			var quest = _guide.GetQuestByDbName(dbName);
			if (quest != null)
				keys.Add(quest.Key);
		}

		foreach (var nodeKey in _reader.ReadNavSetKeys())
		{
			var node = _guide.GetNode(nodeKey);
			if (node?.Type == NodeType.Quest)
				keys.Add(node.Key);
		}

		foreach (var dbName in _reader.ReadTrackedQuests())
		{
			var quest = _guide.GetQuestByDbName(dbName);
			if (quest != null)
				keys.Add(quest.Key);
		}

		foreach (var dbName in _reader.ReadImplicitlyAvailableQuestDbNames())
		{
			_reader.ReadQuestActive(dbName);
			var quest = _guide.GetQuestByDbName(dbName);
			if (quest != null)
				keys.Add(quest.Key);
		}

		return new NavigableQuestSet(keys.OrderBy(key => key, StringComparer.Ordinal).ToArray());
	}
}

public sealed class NavigableQuestSet
{
	public IReadOnlyList<string> Keys { get; }

	public NavigableQuestSet(IReadOnlyList<string> keys) => Keys = keys;

	public override bool Equals(object? obj) =>
		obj is NavigableQuestSet other && Keys.SequenceEqual(other.Keys);

	public override int GetHashCode() => Keys.Count;
}

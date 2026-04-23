using AdventureGuide.Incremental;
using AdventureGuide.State;

namespace AdventureGuide.Navigation.Queries;

public sealed class SelectorTargetSetQuery
{
	private readonly GuideReader _reader;
	private readonly Query<Unit, NavigableQuestSet> _navigableQuests;

	public Query<Unit, SelectorTargetSet> Query { get; }

	public SelectorTargetSetQuery(
		Engine<FactKey> engine,
		GuideReader reader,
		NavigableQuestsQuery navigableQuests)
		: this(engine, reader, navigableQuests.Query)
	{
	}

	internal SelectorTargetSetQuery(
		Engine<FactKey> engine,
		GuideReader reader,
		Query<Unit, NavigableQuestSet> navigableQuests)
	{
		_reader = reader;
		_navigableQuests = navigableQuests;
		Query = engine.DefineQuery<Unit, SelectorTargetSet>(
			name: "SelectorTargetSet",
			compute: Compute);
	}

	private SelectorTargetSet Compute(ReadContext<FactKey> ctx, Unit _)
	{
		var keys = new HashSet<string>(StringComparer.Ordinal);
		var navigable = ctx.Read(_navigableQuests, Unit.Value);
		for (int i = 0; i < navigable.Keys.Count; i++)
			keys.Add(navigable.Keys[i]);

		foreach (var key in _reader.ReadNavSetKeys())
			keys.Add(key);

		return new SelectorTargetSet(keys.OrderBy(key => key, StringComparer.Ordinal).ToArray());
	}
}

public sealed class SelectorTargetSet : IEquatable<SelectorTargetSet>
{
	public SelectorTargetSet(IReadOnlyList<string> keys) => Keys = keys;

	public IReadOnlyList<string> Keys { get; }

	public bool Equals(SelectorTargetSet? other)
	{
		if (other is null)
			return false;
		if (ReferenceEquals(this, other))
			return true;
		return Keys.SequenceEqual(other.Keys);
	}

	public override bool Equals(object? obj) => Equals(obj as SelectorTargetSet);

	public override int GetHashCode() => Keys.Count;
}

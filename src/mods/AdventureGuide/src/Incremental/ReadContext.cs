namespace AdventureGuide.Incremental;

/// <summary>Passed to every query's compute function. Records fact dependencies
/// explicitly via <see cref="RecordFact"/> and stitches query-to-query
/// dependencies transparently via <see cref="Read"/>.</summary>
public sealed class ReadContext<TFactKey> where TFactKey : notnull
{
	private readonly Engine<TFactKey> _engine;

	internal ReadContext(Engine<TFactKey> engine) => _engine = engine;

	internal HashSet<TFactKey> Facts { get; } = new();
	internal HashSet<(int QueryId, object Key)> QueryDeps { get; } = new();

	public void RecordFact(TFactKey fact) => Facts.Add(fact);

	public TValue Read<TKey, TValue>(Query<TKey, TValue> query, TKey key) where TKey : notnull
	{
		QueryDeps.Add((query.Id, (object)key));
		return _engine.Read(query, key);
	}

	public TValue ReadUncached<TKey, TValue>(Query<TKey, TValue> query, TKey key)
		where TKey : notnull
	{
		QueryDeps.Add((query.Id, (object)key));
		return _engine.ReadUncached(query, key);
	}
}

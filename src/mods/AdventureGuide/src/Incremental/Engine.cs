namespace AdventureGuide.Incremental;

/// <summary>Salsa-shaped incremental query engine. Memoises <c>(query, key)</c>
/// entries; recomputes lazily on read when a recorded fact or sub-query dep has
/// a newer revision than the entry. Backdating (value-equality on recomputed
/// outputs) suppresses ripples when a recompute produces an unchanged value.</summary>
public sealed class Engine<TFactKey> where TFactKey : notnull
{
	private int _revision;
	private int _nextQueryId;
	private readonly Dictionary<TFactKey, int> _factRevisions = new();
	private readonly Dictionary<(int, object), Entry> _entries = new();
	private readonly Dictionary<TFactKey, HashSet<(int, object)>> _entriesByFact = new();
	private readonly Stack<(int, object)> _computeStack = new();

	public Query<TKey, TValue> DefineQuery<TKey, TValue>(
		string name,
		Func<ReadContext<TFactKey>, TKey, TValue> compute) where TKey : notnull
	{
		int id = _nextQueryId++;
		return new Query<TKey, TValue>(name, id,
			(ctxObj, key) => compute((ReadContext<TFactKey>)ctxObj, (TKey)key));
	}

	public TValue Read<TKey, TValue>(Query<TKey, TValue> query, TKey key) where TKey : notnull
	{
		var entryKey = (query.Id, (object)key);
		if (_computeStack.Contains(entryKey))
			throw new InvalidOperationException(
				$"Cycle detected: query '{query.Name}' with key '{key}' is already being computed.");

		if (_entries.TryGetValue(entryKey, out var entry) && !IsStale(entry))
			return (TValue)entry.Value!;

		return (TValue)Recompute(query, key, entryKey)!;
	}

	public IReadOnlyCollection<QueryRef> InvalidateFacts(IEnumerable<TFactKey> changed)
	{
		var affected = new HashSet<(int, object)>();
		foreach (var fact in changed)
		{
			_revision++;
			_factRevisions[fact] = _revision;
			if (_entriesByFact.TryGetValue(fact, out var dependents))
				affected.UnionWith(dependents);
		}
		// Dependents of dependents get picked up lazily by IsStale() on next read.

		var refs = new List<QueryRef>(affected.Count);
		foreach (var (queryId, key) in affected)
		{
			if (_entries.TryGetValue((queryId, key), out var entry))
				refs.Add(new QueryRef(entry.QueryName, key));
		}
		return refs;
	}

	private bool IsStale(Entry entry)
	{
		foreach (var fact in entry.Facts)
			if (_factRevisions.TryGetValue(fact, out int rev) && rev > entry.Revision)
				return true;

		foreach (var depKey in entry.QueryDeps)
		{
			var lookupKey = (depKey.QueryId, depKey.Key);
			if (!_entries.TryGetValue(lookupKey, out var depEntry))
				return true;

			if (IsStale(depEntry))
				depEntry = depEntry.Refresh();

			if (depEntry.Revision > entry.Revision)
				return true;
		}
		return false;
	}

	private object? Recompute<TKey, TValue>(Query<TKey, TValue> query, TKey key, (int, object) entryKey)
		where TKey : notnull
	{
		_computeStack.Push(entryKey);
		var ctx = new ReadContext<TFactKey>(this);
		TValue value;
		try
		{
			value = (TValue)query.Compute(ctx, key)!;
		}
		finally
		{
			_computeStack.Pop();
		}

		bool existed = _entries.TryGetValue(entryKey, out var prior);
		bool changed = !existed || !Equals(prior.Value, value);

		// Unsubscribe old fact→entry reverse deps before re-subscribing.
		if (existed)
		{
			foreach (var oldFact in prior.Facts)
				if (_entriesByFact.TryGetValue(oldFact, out var set))
					set.Remove(entryKey);
		}

		int newRevision = changed ? ++_revision : prior.Revision;
		var entry = new Entry(
			query.Name,
			ctx.Facts,
			ctx.QueryDeps,
			value,
			newRevision,
			() =>
			{
				Recompute(query, key, entryKey);
				return _entries[entryKey];
			});
		_entries[entryKey] = entry;

		foreach (var fact in ctx.Facts)
		{
			if (!_entriesByFact.TryGetValue(fact, out var set))
				_entriesByFact[fact] = set = new HashSet<(int, object)>();
			set.Add(entryKey);
		}

		return value;
	}

	private sealed class Entry
	{
		public Entry(
			string queryName,
			HashSet<TFactKey> facts,
			HashSet<(int QueryId, object Key)> queryDeps,
			object? value,
			int revision,
			Func<Entry> refresh)
		{
			QueryName = queryName;
			Facts = facts;
			QueryDeps = queryDeps;
			Value = value;
			Revision = revision;
			Refresh = refresh;
		}

		public string QueryName { get; }
		public HashSet<TFactKey> Facts { get; }
		public HashSet<(int QueryId, object Key)> QueryDeps { get; }
		public object? Value { get; }
		public int Revision { get; }
		public Func<Entry> Refresh { get; }
	}
}

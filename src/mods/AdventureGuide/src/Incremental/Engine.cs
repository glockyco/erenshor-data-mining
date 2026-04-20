namespace AdventureGuide.Incremental;

/// <summary>Salsa-shaped incremental query engine. Memoises <c>(query, key)</c>
/// entries; recomputes lazily on read when a recorded fact or sub-query dep has
/// a newer revision than the entry. Backdating (value-equality on recomputed
/// outputs) suppresses ripples when a recompute produces an unchanged value.
///
/// <para><b>Read semantics.</b> When <see cref="Read{TKey,TValue}"/> recomputes
/// an entry and finds the new value equal (via <see cref="object.Equals(object,object)"/>)
/// to the prior cached value, the engine returns the <i>prior instance</i>, not
/// the freshly-computed one. Consumers may rely on reference identity as a
/// proxy for value identity: a returned reference that equals the last
/// reference observed implies no content change. Returned values must be
/// treated as immutable — the engine reuses instances, and mutating one
/// corrupts the cache.</para></summary>
public sealed class Engine<TFactKey> where TFactKey : notnull
{
	private readonly object _ownerToken = new();
	private int _revision;
	private int _nextQueryId;
	private readonly Dictionary<TFactKey, int> _factRevisions = new();
	private readonly Dictionary<(int, object), Entry> _entries = new();
	private readonly Dictionary<TFactKey, HashSet<(int, object)>> _entriesByFact = new();

	// Ambient read context for the compute currently running on this thread.
	// Trackers call Ambient?.RecordFact(...) to subscribe the current compute to
	// a fact without the query needing to know which keys will be touched.
	[ThreadStatic]
	private static ReadContext<TFactKey>? _ambient;
	internal static ReadContext<TFactKey>? Ambient => _ambient;
	// Per-query recomputer so IsStale can refresh a dep entry by (queryId, key)
	// without knowing its concrete type. One delegate per query, not per entry.
	private readonly Dictionary<int, Action<object>> _recomputers = new();
	private readonly Stack<(int, object)> _computeStack = new();

	public int Revision => _revision;
	public Query<TKey, TValue> DefineQuery<TKey, TValue>(
		string name,
		Func<ReadContext<TFactKey>, TKey, TValue> compute) where TKey : notnull
	{
		int id = _nextQueryId++;
		var query = new Query<TKey, TValue>(name, id, _ownerToken,
			(ctxObj, key) => compute((ReadContext<TFactKey>)ctxObj, (TKey)key));
		_recomputers[id] = keyObj => Recompute(query, (TKey)keyObj, (id, keyObj));
		return query;
	}

	public TValue Read<TKey, TValue>(Query<TKey, TValue> query, TKey key) where TKey : notnull
	{
		if (!ReferenceEquals(query.OwnerToken, _ownerToken))
			throw new InvalidOperationException(
				$"Query '{query.Name}' does not belong to this engine.");

		var entryKey = (query.Id, (object)key);
		if (_computeStack.Contains(entryKey))
			throw new InvalidOperationException(
				$"Cycle detected: query '{query.Name}' with key '{key}' is already being computed.");

		if (_entries.TryGetValue(entryKey, out var entry) && !IsStale(entry))
			return (TValue)entry.Value!;

		return (TValue)Recompute(query, key, entryKey)!;
	}

	/// <summary>Forces recompute of <c>(query, key)</c> regardless of cache state,
	/// rebinds fact/sub-query deps from the new compute, and returns the fresh
	/// value. Used for diagnostic reads that must walk compute paths even when the
	/// cached entry is still valid (e.g. tracing with a tracer attached).</summary>
	public TValue ReadUncached<TKey, TValue>(Query<TKey, TValue> query, TKey key) where TKey : notnull
	{
		if (!ReferenceEquals(query.OwnerToken, _ownerToken))
			throw new InvalidOperationException(
				$"Query '{query.Name}' does not belong to this engine.");

		var entryKey = (query.Id, (object)key);
		if (_computeStack.Contains(entryKey))
			throw new InvalidOperationException(
				$"Cycle detected: query '{query.Name}' with key '{key}' is already being computed.");

		return (TValue)Recompute(query, key, entryKey)!;
	}

	/// <summary>Marks cache entries whose recorded facts were bumped. Returned set
	/// lists directly-affected entries only; transitive dependents become stale
	/// lazily on the next read via <see cref="IsStale"/>. The return value is
	/// diagnostic; no branching logic depends on its completeness.</summary>
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

		var refs = new List<QueryRef>(affected.Count);
		foreach (var (queryId, key) in affected)
		{
			if (_entries.TryGetValue((queryId, key), out var entry))
				refs.Add(new QueryRef(entry.QueryName, key));
		}
		return refs;
	}

	// Deep verification: a stale dep is refreshed in place so its post-recompute
	// revision reflects backdating. This keeps the "backdating suppresses ripple"
	// property: if a dep recomputes to the same value, its revision is unchanged,
	// and we stay fresh without a speculative recompute of our own.
	//
	// The recursion depth is bounded by the query graph's depth (shallow in
	// practice — Plan A tops out at 3). The side-effect is contained: recompute
	// itself is idempotent on stable inputs and the compute stack catches cycles.
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
			{
				_recomputers[depKey.QueryId](depKey.Key);
				depEntry = _entries[lookupKey];
			}

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
		var priorAmbient = _ambient;
		_ambient = ctx;
		TValue value;
		try
		{
			value = (TValue)query.Compute(ctx, key)!;
		}
		finally
		{
			_ambient = priorAmbient;
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

		// When the recomputed value equals the prior, return the prior
		// instance. This is the engine's identity-preservation contract:
		// Equals(prior, new) implies the caller sees the same reference across
		// reads, so ReferenceEquals is a correct proxy for "did this value
		// change". Treating returned values as immutable is a prerequisite
		// (documented on Engine<T>).
		object? storedValue = changed ? value : prior!.Value;
		int newRevision = changed ? ++_revision : prior!.Revision;
		var entry = new Entry(query.Name, ctx.Facts, ctx.QueryDeps, storedValue, newRevision);
		_entries[entryKey] = entry;

		foreach (var fact in ctx.Facts)
		{
		    if (!_entriesByFact.TryGetValue(fact, out var set))
		        _entriesByFact[fact] = set = new HashSet<(int, object)>();
		    set.Add(entryKey);
		}

		return storedValue;
	}

	private sealed class Entry
	{
		public Entry(string queryName, HashSet<TFactKey> facts, HashSet<(int QueryId, object Key)> queryDeps, object? value, int revision)
		{
			QueryName = queryName;
			Facts = facts;
			QueryDeps = queryDeps;
			Value = value;
			Revision = revision;
		}

		public string QueryName { get; }
		public HashSet<TFactKey> Facts { get; }
		public HashSet<(int QueryId, object Key)> QueryDeps { get; }
		public object? Value { get; }
		public int Revision { get; }
	}
}

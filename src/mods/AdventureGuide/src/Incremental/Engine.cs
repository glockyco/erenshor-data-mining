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
	private long _revision;
	private int _nextQueryId;
	private readonly Dictionary<TFactKey, long> _factRevisions = new();
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
	private readonly HashSet<string> _queryNames = new(StringComparer.Ordinal);

	// Per-query counters. Keyed by queryId so lookups stay O(1) on the hot
	// path; surfaced by GetStatistics with the name mapping.
	private readonly Dictionary<int, string> _queryNamesById = new();
	private readonly Dictionary<int, long> _queryComputes = new();
	private readonly Dictionary<int, long> _queryBackdates = new();
	private readonly Dictionary<int, long> _queryStaleReads = new();
	private readonly Dictionary<int, long> _queryFreshReads = new();
	private long _totalComputes;
	private long _totalBackdates;
	private long _totalStaleReads;
	private long _totalFreshReads;
	private long _totalInvalidations;
	private IEngineTracer<TFactKey>? _tracer;

	public long Revision => _revision;

	/// <summary>Test-only view of the fact-to-dependent-entries reverse index.
	/// Consumers must not read this in production code; it is exposed via
	/// InternalsVisibleTo to pin invariants like "empty sets are cleaned up."</summary>
	internal IReadOnlyDictionary<TFactKey, HashSet<(int, object)>> EntriesByFactForTests => _entriesByFact;

	/// <summary>Registers a new query. Query names must be unique within an
	/// engine; a duplicate name throws <see cref="InvalidOperationException"/>
	/// so diagnostic output (<see cref="QueryRef.ToString"/>, tracer
	/// callbacks) is unambiguous.</summary>
	public Query<TKey, TValue> DefineQuery<TKey, TValue>(
		string name,
		Func<ReadContext<TFactKey>, TKey, TValue> compute) where TKey : notnull
	{
		if (!_queryNames.Add(name))
			throw new InvalidOperationException(
				$"A query named '{name}' is already registered on this engine.");
		int id = _nextQueryId++;
		_queryNamesById[id] = name;
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
		{
			_totalFreshReads++;
			IncrementPerQuery(_queryFreshReads, query.Id);
			return (TValue)entry.Value!;
		}

		_totalStaleReads++;
		IncrementPerQuery(_queryStaleReads, query.Id);
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
	/// diagnostic; no branching logic depends on its completeness.
	///
	/// <para>Must not be called from inside a query compute. Invalidation is an
	/// at-rest operation; mid-compute calls would bump <c>_revision</c> under an
	/// active ambient <see cref="ReadContext{TFactKey}"/> and produce surprising
	/// staleness semantics for the currently-running query. A re-entrant call
	/// throws <see cref="InvalidOperationException"/>.</para></summary>
	public IReadOnlyCollection<QueryRef> InvalidateFacts(IEnumerable<TFactKey> changed)
	{
		if (_computeStack.Count > 0)
			throw new InvalidOperationException(
				"InvalidateFacts may not be called from inside a query compute.");

		var materialised = changed as IReadOnlyCollection<TFactKey> ?? changed.ToList();
		var affected = new HashSet<(int, object)>();
		foreach (var fact in materialised)
		{
			_revision++;
			_factRevisions[fact] = _revision;
			_totalInvalidations++;
			if (_entriesByFact.TryGetValue(fact, out var dependents))
				affected.UnionWith(dependents);
		}

		var refs = new List<QueryRef>(affected.Count);
		foreach (var (queryId, key) in affected)
		{
			if (_entries.TryGetValue((queryId, key), out var entry))
				refs.Add(new QueryRef(entry.QueryName, key));
		}

		_tracer?.OnInvalidate(materialised, affected.Count);
		return refs;
	}

	/// <summary>Returns the cached value for <c>(query, key)</c> without forcing
	/// recompute. Returns <c>false</c> when no entry exists. Returns <c>true</c>
	/// and the cached value when an entry exists, regardless of staleness — the
	/// caller is responsible for deciding whether the value is fresh enough.
	///
	/// <para>Intended for diagnostic overlays and tests that want to inspect the
	/// cache without triggering side-effects. Production hot-paths that need a
	/// current value should use <see cref="Read{TKey,TValue}"/>.</para></summary>
	public bool TryPeek<TKey, TValue>(Query<TKey, TValue> query, TKey key, out TValue value) where TKey : notnull
	{
		if (!ReferenceEquals(query.OwnerToken, _ownerToken))
			throw new InvalidOperationException(
				$"Query '{query.Name}' does not belong to this engine.");

		if (_entries.TryGetValue((query.Id, (object)key), out var entry))
		{
			value = (TValue)entry.Value!;
			return true;
		}
		value = default!;
		return false;
	}

	/// <summary>Removes the cached entry for <c>(query, key)</c> and unsubscribes
	/// it from every recorded fact. Returns <c>true</c> if an entry was
	/// removed. Consumers drive eviction; the engine performs no automatic
	/// eviction and is not a general-purpose cache.</summary>
	public bool Evict<TKey, TValue>(Query<TKey, TValue> query, TKey key) where TKey : notnull
	{
		if (!ReferenceEquals(query.OwnerToken, _ownerToken))
			throw new InvalidOperationException(
				$"Query '{query.Name}' does not belong to this engine.");
		if (_computeStack.Count > 0)
			throw new InvalidOperationException(
				"Evict may not be called from inside a query compute.");

		var entryKey = (query.Id, (object)key);
		if (!_entries.TryGetValue(entryKey, out var entry))
			return false;

		UnsubscribeEntry(entryKey, entry);
		_entries.Remove(entryKey);
		return true;
	}

	/// <summary>Removes every cached entry for the given query. Returns the number
	/// of entries removed. Unsubscribes each from its recorded facts.</summary>
	public int EvictQuery<TKey, TValue>(Query<TKey, TValue> query) where TKey : notnull
	{
		if (!ReferenceEquals(query.OwnerToken, _ownerToken))
			throw new InvalidOperationException(
				$"Query '{query.Name}' does not belong to this engine.");
		if (_computeStack.Count > 0)
			throw new InvalidOperationException(
				"EvictQuery may not be called from inside a query compute.");

		var victims = new List<(int, object)>();
		foreach (var kvp in _entries)
		{
			if (kvp.Key.Item1 == query.Id)
				victims.Add(kvp.Key);
		}
		foreach (var entryKey in victims)
		{
			UnsubscribeEntry(entryKey, _entries[entryKey]);
			_entries.Remove(entryKey);
		}
		return victims.Count;
	}

	/// <summary>Drops all cache state while preserving query definitions. Clears
	/// entries, fact revisions, the reverse index, per-query and total
	/// counters, and resets <c>_revision</c> to zero. Intended for scenarios
	/// that reset all observed external state (for example character reload);
	/// not a routine operation.</summary>
	public void Reset()
	{
		if (_computeStack.Count > 0)
			throw new InvalidOperationException(
				"Reset may not be called from inside a query compute.");
		_entries.Clear();
		_entriesByFact.Clear();
		_factRevisions.Clear();
		_revision = 0;
		_queryComputes.Clear();
		_queryBackdates.Clear();
		_queryStaleReads.Clear();
		_queryFreshReads.Clear();
		_totalComputes = 0;
		_totalBackdates = 0;
		_totalStaleReads = 0;
		_totalFreshReads = 0;
		_totalInvalidations = 0;
	}

	/// <summary>Installs an optional tracer that receives hooks for every
	/// recompute and invalidation. Pass <c>null</c> to remove. The engine
	/// holds a single tracer at a time; callers that need fan-out should
	/// compose their own broadcasting implementation.</summary>
	public void SetTracer(IEngineTracer<TFactKey>? tracer) => _tracer = tracer;

	/// <summary>Returns a read-only snapshot of engine telemetry. Counters
	/// are monotonic for the lifetime of the engine except <c>EntryCount</c>,
	/// which reflects the live cache size at snapshot time. <c>Reset</c>
	/// zeroes all counters.</summary>
	public EngineStatistics GetStatistics()
	{
		var perQuery = new Dictionary<string, EngineQueryStatistics>(StringComparer.Ordinal);
		foreach (var kvp in _queryNamesById)
		{
			_queryComputes.TryGetValue(kvp.Key, out long computes);
			_queryBackdates.TryGetValue(kvp.Key, out long backdates);
			_queryStaleReads.TryGetValue(kvp.Key, out long stale);
			_queryFreshReads.TryGetValue(kvp.Key, out long fresh);
			perQuery[kvp.Value] = new EngineQueryStatistics(computes, backdates, stale, fresh);
		}
		return new EngineStatistics(
			_entries.Count,
			_totalComputes,
			_totalBackdates,
			_totalStaleReads,
			_totalFreshReads,
			_totalInvalidations,
			perQuery);
	}

	private void UnsubscribeEntry((int, object) entryKey, Entry entry)
	{
		foreach (var fact in entry.Facts)
		{
			if (!_entriesByFact.TryGetValue(fact, out var set))
				continue;
			set.Remove(entryKey);
			if (set.Count == 0)
				_entriesByFact.Remove(fact);
		}
	}

	// Deep verification: a stale dep is refreshed in place so its post-recompute
	// revision reflects backdating. This keeps the "backdating suppresses ripple"
	// property: if a dep recomputes to the same value, its revision is unchanged,
	// and we stay fresh without a speculative recompute of our own.
	//
	// Staleness compares fact and dep revisions against the entry's
	// LastVerifiedRevision — the global tick at which this entry was last
	// confirmed current. After a backdated recompute, LastVerifiedRevision
	// advances even though Revision stays put, so subsequent reads with no
	// further fact bumps skip the recompute entirely. Without this split,
	// every Read after a fact bump would recompute the entry forever, since
	// the entry's Revision stays behind the bumped fact's revision.
	//
	// The recursion depth is bounded by the query graph's depth (shallow in
	// practice — Plan A tops out at 3). The side-effect is contained: recompute
	// itself is idempotent on stable inputs and the compute stack catches cycles.
	private bool IsStale(Entry entry)
	{
		foreach (var fact in entry.Facts)
			if (_factRevisions.TryGetValue(fact, out long rev) && rev > entry.LastVerifiedRevision)
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

			if (depEntry.Revision > entry.LastVerifiedRevision)
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
		long computeStart = System.Diagnostics.Stopwatch.GetTimestamp();
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
		long computeTicks = System.Diagnostics.Stopwatch.GetTimestamp() - computeStart;

		bool existed = _entries.TryGetValue(entryKey, out var prior);
		bool changed = !existed || !Equals(prior.Value, value);

		// Unsubscribe old fact→entry reverse deps before re-subscribing. Shared
		// with `Evict` / `EvictQuery` via `UnsubscribeEntry` so orphan cleanup
		// logic lives in one place.
		if (existed)
			UnsubscribeEntry(entryKey, prior!);

		// When the recomputed value equals the prior, return the prior
		// instance. This is the engine's identity-preservation contract:
		// Equals(prior, new) implies the caller sees the same reference across
		// reads, so ReferenceEquals is a correct proxy for "did this value
		// change". Treating returned values as immutable is a prerequisite
		// (documented on Engine<T>).
		object? storedValue = changed ? value : prior!.Value;
		long newRevision = changed ? ++_revision : prior!.Revision;
		var entry = new Entry(query.Name, ctx.Facts, ctx.QueryDeps, storedValue, newRevision, lastVerifiedRevision: _revision);
		_entries[entryKey] = entry;

		foreach (var fact in ctx.Facts)
		{
			if (!_entriesByFact.TryGetValue(fact, out var set))
				_entriesByFact[fact] = set = new HashSet<(int, object)>();
			set.Add(entryKey);
		}

		_totalComputes++;
		IncrementPerQuery(_queryComputes, query.Id);
		if (!changed)
		{
			_totalBackdates++;
			IncrementPerQuery(_queryBackdates, query.Id);
		}
		_tracer?.OnRecompute(query.Name, key, backdated: !changed, computeTicks);

		return storedValue;
	}

	private static void IncrementPerQuery(Dictionary<int, long> counters, int queryId)
	{
		counters.TryGetValue(queryId, out long current);
		counters[queryId] = current + 1;
	}

	private sealed class Entry
	{
		public Entry(
			string queryName,
			HashSet<TFactKey> facts,
			HashSet<(int QueryId, object Key)> queryDeps,
			object? value,
			long revision,
			long lastVerifiedRevision)
		{
			QueryName = queryName;
			Facts = facts;
			QueryDeps = queryDeps;
			Value = value;
			Revision = revision;
			LastVerifiedRevision = lastVerifiedRevision;
		}

		public string QueryName { get; }
		public HashSet<TFactKey> Facts { get; }
		public HashSet<(int QueryId, object Key)> QueryDeps { get; }
		public object? Value { get; }

		/// <summary>Global revision at the time this entry's value last changed.
		/// Dependents compare their own <see cref="Revision"/> against this to
		/// decide whether they need to ripple-recompute.</summary>
		public long Revision { get; }

		/// <summary>Global revision at the time this entry's recorded facts and
		/// sub-query deps were last verified to be current. Used by
		/// <see cref="Engine{TFactKey}.IsStale"/> to skip redundant recomputes
		/// when an entry has already been verified against a fact bump that did
		/// not produce a value change.</summary>
		public long LastVerifiedRevision { get; }
	}
}

namespace AdventureGuide.Incremental;

/// <summary>Read-only snapshot of engine telemetry. Returned by
/// <see cref="Engine{TFactKey}.GetStatistics"/>. All counters are
/// monotonic for the lifetime of the engine except <c>EntryCount</c>,
/// which reflects the live cache size at snapshot time.</summary>
public readonly struct EngineStatistics
{
	internal EngineStatistics(
		int entryCount,
		long totalComputes,
		long totalBackdates,
		long totalStaleReads,
		long totalFreshReads,
		long totalInvalidations,
		IReadOnlyDictionary<string, EngineQueryStatistics> perQuery)
	{
		EntryCount = entryCount;
		TotalComputes = totalComputes;
		TotalBackdates = totalBackdates;
		TotalStaleReads = totalStaleReads;
		TotalFreshReads = totalFreshReads;
		TotalInvalidations = totalInvalidations;
		PerQuery = perQuery;
	}

	/// <summary>Number of live cache entries at snapshot time.</summary>
	public int EntryCount { get; }

	/// <summary>Cumulative recompute invocations across all queries.</summary>
	public long TotalComputes { get; }

	/// <summary>Cumulative recomputes whose value was equal to the prior
	/// cached value and therefore returned the prior instance.</summary>
	public long TotalBackdates { get; }

	/// <summary>Cumulative <c>Read</c> calls that hit a stale entry and
	/// triggered a recompute.</summary>
	public long TotalStaleReads { get; }

	/// <summary>Cumulative <c>Read</c> calls that returned a cached entry
	/// without recomputing.</summary>
	public long TotalFreshReads { get; }

	/// <summary>Cumulative fact-invalidation operations (one per fact passed
	/// to <c>InvalidateFacts</c>, not one per batch call).</summary>
	public long TotalInvalidations { get; }

	/// <summary>Per-query breakdown keyed by query name.</summary>
	public IReadOnlyDictionary<string, EngineQueryStatistics> PerQuery { get; }
}

/// <summary>Per-query counters. Each counter is monotonic for the lifetime
/// of the engine (reset to zero by <see cref="Engine{TFactKey}.Reset"/>).</summary>
public readonly struct EngineQueryStatistics
{
	internal EngineQueryStatistics(
		long computes,
		long backdates,
		long staleReads,
		long freshReads)
	{
		Computes = computes;
		Backdates = backdates;
		StaleReads = staleReads;
		FreshReads = freshReads;
	}

	public long Computes { get; }
	public long Backdates { get; }
	public long StaleReads { get; }
	public long FreshReads { get; }
}

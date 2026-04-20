namespace AdventureGuide.Incremental;

/// <summary>Optional callback hooks for engine-level events. Plug in via
/// <see cref="Engine{TFactKey}.SetTracer"/>. The engine calls these on the
/// hot path; implementations must be allocation-free or amortise their cost
/// (for example by recording into a ring buffer).</summary>
public interface IEngineTracer<TFactKey> where TFactKey : notnull
{
	/// <summary>Called after every recompute. <paramref name="backdated"/> is
	/// true when the recomputed value was equal to the prior cached value
	/// and the engine returned the prior instance.</summary>
	void OnRecompute(string queryName, object key, bool backdated, long computeTicks);

	/// <summary>Called once per <see cref="Engine{TFactKey}.InvalidateFacts"/>
	/// call. <paramref name="directAffected"/> is the number of cache entries
	/// directly subscribed to one of the bumped facts; transitive dependents
	/// are not counted.</summary>
	void OnInvalidate(IReadOnlyCollection<TFactKey> facts, int directAffected);
}

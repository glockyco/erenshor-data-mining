namespace AdventureGuide.Incremental;

/// <summary>Untyped handle identifying a specific <c>(query, key)</c> cache entry.
/// Returned by the engine's invalidation methods so callers can observe which
/// entries were marked stale without leaking the engine's internal cache type.</summary>
public readonly struct QueryRef : IEquatable<QueryRef>
{
	internal QueryRef(string queryName, object key)
	{
		QueryName = queryName;
		Key = key;
	}

	public string QueryName { get; }
	public object Key { get; }

	public bool Equals(QueryRef other) =>
		QueryName == other.QueryName && Equals(Key, other.Key);

	public override bool Equals(object? obj) => obj is QueryRef other && Equals(other);
	public override int GetHashCode() => HashCode.Combine(QueryName, Key);
	public override string ToString() => $"{QueryName}({Key})";
}

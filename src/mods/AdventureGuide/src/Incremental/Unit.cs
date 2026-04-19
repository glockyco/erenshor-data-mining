namespace AdventureGuide.Incremental;

/// <summary>Singleton key for queries with no meaningful key dimension.</summary>
public readonly struct Unit : IEquatable<Unit>
{
	public static Unit Value { get; } = default;

	public bool Equals(Unit other) => true;

	public override bool Equals(object? obj) => obj is Unit;

	public override int GetHashCode() => 0;
}

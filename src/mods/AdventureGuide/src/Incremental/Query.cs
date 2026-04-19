namespace AdventureGuide.Incremental;

/// <summary>Typed handle for a query registered with an <see cref="Engine{TFactKey}"/>.
/// Opaque to callers; only the engine that created it can read it.</summary>
public sealed class Query<TKey, TValue> where TKey : notnull
{
	internal Query(string name, int id, object ownerToken, Func<object, TKey, TValue> compute)
	{
		Name = name;
		Id = id;
		OwnerToken = ownerToken;
		Compute = compute;
	}

	internal string Name { get; }
	internal int Id { get; }
	internal object OwnerToken { get; }
	internal Func<object, TKey, TValue> Compute { get; }
}

using AdventureGuide.Resolution;

namespace AdventureGuide.Navigation;

/// <summary>
/// Immutable selector-facing snapshot of one maintained navigation target list
/// for a specific scene. The snapshot preserves the shared target-list
/// reference so callers can detect whether a key's resolved state actually
/// changed.
/// </summary>
public sealed class NavigationTargetSnapshot : IEquatable<NavigationTargetSnapshot>
{
	public NavigationTargetSnapshot(
		string nodeKey,
		string scene,
		IReadOnlyList<ResolvedQuestTarget> targets)
	{
		NodeKey = nodeKey;
		Scene = scene;
		Targets = targets;
	}

	public string NodeKey { get; }
	public string Scene { get; }
	public IReadOnlyList<ResolvedQuestTarget> Targets { get; }

	public bool Equals(NavigationTargetSnapshot? other)
	{
		if (other is null)
			return false;
		if (ReferenceEquals(this, other))
			return true;
		return NodeKey == other.NodeKey
			&& Scene == other.Scene
			&& ReferenceEquals(Targets, other.Targets);
	}

	public override bool Equals(object? obj) => Equals(obj as NavigationTargetSnapshot);

	public override int GetHashCode() => HashCode.Combine(NodeKey, Scene, Targets);
}

/// <summary>
/// Immutable maintained view of all selector target resolutions for one scene.
/// Keeps snapshots ordered by node key and indexed for selector-friendly lookup.
/// </summary>
public sealed class NavigationTargetSnapshots : IEquatable<NavigationTargetSnapshots>
{
	private readonly IReadOnlyDictionary<string, NavigationTargetSnapshot> _byNodeKey;

	public NavigationTargetSnapshots(
		string scene,
		IReadOnlyList<NavigationTargetSnapshot> snapshots)
	{
		Scene = scene;
		Snapshots = snapshots;
		_byNodeKey = snapshots.Count == 0
			? EmptyByNodeKey
			: snapshots.ToDictionary(snapshot => snapshot.NodeKey, StringComparer.Ordinal);
	}

	private static IReadOnlyDictionary<string, NavigationTargetSnapshot> EmptyByNodeKey { get; } =
		new Dictionary<string, NavigationTargetSnapshot>(StringComparer.Ordinal);

	public string Scene { get; }
	public IReadOnlyList<NavigationTargetSnapshot> Snapshots { get; }

	public bool TryGet(string nodeKey, out NavigationTargetSnapshot snapshot) =>
		_byNodeKey.TryGetValue(nodeKey, out snapshot!);

	public bool Equals(NavigationTargetSnapshots? other)
	{
		if (other is null)
			return false;
		if (ReferenceEquals(this, other))
			return true;
		return Scene == other.Scene && Snapshots.SequenceEqual(other.Snapshots);
	}

	public override bool Equals(object? obj) => Equals(obj as NavigationTargetSnapshots);

	public override int GetHashCode() => HashCode.Combine(Scene, Snapshots.Count);
}

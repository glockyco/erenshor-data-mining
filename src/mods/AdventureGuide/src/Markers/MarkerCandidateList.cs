namespace AdventureGuide.Markers;

/// <summary>
/// Ordered list of <see cref="MarkerCandidate"/> values produced by
/// <see cref="Queries.MarkerCandidatesQuery"/>. Wrapping the collection in a
/// value-equatable container lets the incremental engine's backdating logic
/// suppress dependent recomputes when a scene's candidate set is unchanged.
/// </summary>
public sealed class MarkerCandidateList : IEquatable<MarkerCandidateList>
{
	public MarkerCandidateList(IReadOnlyList<MarkerCandidate> candidates)
	{
		Candidates = candidates;
	}

	public IReadOnlyList<MarkerCandidate> Candidates { get; }

	public bool Equals(MarkerCandidateList? other)
	{
		if (other is null)
			return false;
		if (ReferenceEquals(this, other))
			return true;
		return Candidates.SequenceEqual(other.Candidates);
	}

	public override bool Equals(object? obj) => Equals(obj as MarkerCandidateList);

	public override int GetHashCode() => Candidates.Count;
}

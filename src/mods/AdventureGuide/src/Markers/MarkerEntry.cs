using AdventureGuide.Resolution;

namespace AdventureGuide.Markers;

/// <summary>
/// Data for a single world marker. Produced by <see cref="MarkerProjector"/>,
/// consumed by <see cref="MarkerRenderer"/> for rendering.
/// </summary>
public sealed class MarkerEntry
{
	public MarkerEntry(MarkerCandidate candidate)
	{
		Candidate = candidate;
		X = candidate.X;
		Y = candidate.Y;
		Z = candidate.Z;
		SubText = string.Empty;
	}

	public MarkerCandidate Candidate { get; }

	public float X { get; set; }
	public float Y { get; set; }
	public float Z { get; set; }

	public MarkerType Type { get; set; }
	public int Priority { get; set; }
	public string SubText { get; set; }

	public string QuestKey => Candidate.QuestKey;
	public string Scene => Candidate.Scene;
	public string PositionNodeKey => Candidate.PositionNodeKey;
	public string? SourceNodeKey => Candidate.SourceNodeKey;
	public string SourceKey => Candidate.SourceNodeKey ?? Candidate.PositionNodeKey;
	public string DisplayName => Candidate.DisplayName;

	internal static MarkerType ToMarkerType(QuestMarkerKind kind) =>
		kind switch
		{
			QuestMarkerKind.TurnInReady => MarkerType.TurnInReady,
			QuestMarkerKind.TurnInRepeatReady => MarkerType.TurnInRepeatReady,
			QuestMarkerKind.TurnInPending => MarkerType.TurnInPending,
			QuestMarkerKind.Objective => MarkerType.Objective,
			QuestMarkerKind.QuestGiver => MarkerType.QuestGiver,
			QuestMarkerKind.QuestGiverRepeat => MarkerType.QuestGiverRepeat,
			QuestMarkerKind.QuestGiverBlocked => MarkerType.QuestGiverBlocked,
			_ => throw new ArgumentOutOfRangeException(nameof(kind), kind, null),
		};
}

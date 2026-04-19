using AdventureGuide.Resolution;

namespace AdventureGuide.Markers;

/// <summary>
/// Data for a single world marker. Produced by <see cref="MarkerProjector"/>,
/// consumed by <see cref="MarkerRenderer"/> for rendering and per-frame updates.
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

	public SpawnPoint? LiveSpawnPoint { get; set; }
	public NPC? TrackedNPC { get; set; }
	public MiningNode? LiveMiningNode { get; set; }
	public RotChest? LiveRotChest { get; set; }
	public bool IsLootChestTarget { get; set; }

	public string QuestKey => Candidate.QuestKey;
	public string Scene => Candidate.Scene;
	public string PositionNodeKey => Candidate.PositionNodeKey;
	public string? SourceNodeKey => Candidate.SourceNodeKey;
	public string DisplayName => Candidate.DisplayName;
	public bool IsSpawnTimerSlot => Candidate.IsSpawnTimerSlot;

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

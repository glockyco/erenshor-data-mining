namespace AdventureGuide.Markers;

/// <summary>
/// Pure-data render state for a single marker candidate. Produced per-frame by
/// <see cref="MarkerProjector"/> and consumed by
/// <see cref="MarkerProjector"/>. Carries no Unity object references.
/// </summary>
public readonly struct MarkerLiveRenderState
{
	public MarkerLiveRenderState(
		MarkerLiveStatus status,
		(float X, float Y, float Z)? livePosition,
		float respawnSeconds,
		string? unlockReason)
	{
		Status = status;
		LivePosition = livePosition;
		RespawnSeconds = respawnSeconds;
		UnlockReason = unlockReason;
	}

	public MarkerLiveStatus Status { get; }
	public (float X, float Y, float Z)? LivePosition { get; }
	public float RespawnSeconds { get; }
	public string? UnlockReason { get; }

	public static MarkerLiveRenderState Unknown { get; } =
		new(MarkerLiveStatus.Unknown, null, 0f, null);
}

public enum MarkerLiveStatus : byte
{
	Unknown,
	Alive,
	DeadWithCorpse,
	DeadNoCorpse,
	NightLocked,
	UnlockBlocked,
	Disabled,
	PickedUp,
	MiningAvailable,
	MiningMined,
	ZoneReentry,
}

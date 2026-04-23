using AdventureGuide.Markers;

namespace AdventureGuide.State;

public readonly struct LiveSourceSnapshot : IEquatable<LiveSourceSnapshot>
{
	private LiveSourceSnapshot(
		string? sourceNodeKey,
		string? targetNodeKey,
		LiveSourceKind kind,
		LiveSourceOccupancy occupancy,
		bool isActionable,
		LiveSourceAnchor anchor,
		(float X, float Y, float Z)? livePosition,
		(float X, float Y, float Z)? anchoredLivePosition,
		float respawnSeconds,
		string? unlockReason,
		bool requiresZoneReentry)
	{
		SourceNodeKey = sourceNodeKey;
		TargetNodeKey = targetNodeKey;
		Kind = kind;
		Occupancy = occupancy;
		IsActionable = isActionable;
		Anchor = anchor;
		LivePosition = livePosition;
		AnchoredLivePosition = anchoredLivePosition;
		RespawnSeconds = respawnSeconds;
		UnlockReason = unlockReason;
		RequiresZoneReentry = requiresZoneReentry;
	}

	public string? SourceNodeKey { get; }
	public string? TargetNodeKey { get; }
	public LiveSourceKind Kind { get; }
	public LiveSourceOccupancy Occupancy { get; }
	public bool IsActionable { get; }
	public LiveSourceAnchor Anchor { get; }
	public (float X, float Y, float Z)? LivePosition { get; }
	public (float X, float Y, float Z)? AnchoredLivePosition { get; }
	public float RespawnSeconds { get; }
	public string? UnlockReason { get; }
	public bool RequiresZoneReentry { get; }

	public static LiveSourceSnapshot Unknown(string? sourceNodeKey, string? targetNodeKey) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.Unknown, LiveSourceOccupancy.Unknown, false, LiveSourceAnchor.None, null, null, 0f, null, false);

	public static LiveSourceSnapshot Alive(
		string sourceNodeKey,
		string targetNodeKey,
		(float X, float Y, float Z) livePosition,
		(float X, float Y, float Z) anchoredLivePosition) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.Character, LiveSourceOccupancy.Alive, true, LiveSourceAnchor.LiveObject, livePosition, anchoredLivePosition, 0f, null, false);

	public static LiveSourceSnapshot Dead(
		string sourceNodeKey,
		string targetNodeKey,
		(float X, float Y, float Z)? livePosition,
		(float X, float Y, float Z)? anchoredLivePosition,
		float respawnSeconds) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.Character, LiveSourceOccupancy.Dead, false, livePosition.HasValue ? LiveSourceAnchor.LiveObject : LiveSourceAnchor.Source, livePosition, anchoredLivePosition, respawnSeconds, null, false);

	public static LiveSourceSnapshot ZoneReentry(
		string sourceNodeKey,
		string targetNodeKey,
		float respawnSeconds) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.Character, LiveSourceOccupancy.Dead, false, LiveSourceAnchor.Source, null, null, respawnSeconds, null, true);

	public static LiveSourceSnapshot NightLocked(string sourceNodeKey, string targetNodeKey) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.Character, LiveSourceOccupancy.NightLocked, false, LiveSourceAnchor.Source, null, null, 0f, null, false);

	public static LiveSourceSnapshot UnlockBlocked(string sourceNodeKey, string targetNodeKey, string reason) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.Character, LiveSourceOccupancy.UnlockBlocked, false, LiveSourceAnchor.Source, null, null, 0f, reason, false);

	public static LiveSourceSnapshot Disabled(string sourceNodeKey, string targetNodeKey) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.Character, LiveSourceOccupancy.Disabled, false, LiveSourceAnchor.Source, null, null, 0f, null, false);

	public static LiveSourceSnapshot MiningAvailable(string sourceNodeKey, string targetNodeKey) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.MiningNode, LiveSourceOccupancy.Available, true, LiveSourceAnchor.Source, null, null, 0f, null, false);

	public static LiveSourceSnapshot Mined(string sourceNodeKey, string targetNodeKey, float respawnSeconds) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.MiningNode, LiveSourceOccupancy.Mined, false, LiveSourceAnchor.Source, null, null, respawnSeconds, null, false);

	public static LiveSourceSnapshot ItemAvailable(string sourceNodeKey, string targetNodeKey) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.ItemBag, LiveSourceOccupancy.Available, true, LiveSourceAnchor.Source, null, null, 0f, null, false);

	public static LiveSourceSnapshot PickedUp(string sourceNodeKey, string targetNodeKey, float respawnSeconds) =>
		new(sourceNodeKey, targetNodeKey, LiveSourceKind.ItemBag, LiveSourceOccupancy.PickedUp, false, LiveSourceAnchor.Source, null, null, respawnSeconds, null, false);

	public MarkerLiveRenderState ToMarkerRenderState()
	{
		switch (Kind)
		{
			case LiveSourceKind.Character:
				switch (Occupancy)
				{
					case LiveSourceOccupancy.Alive:
						return new MarkerLiveRenderState(MarkerLiveStatus.Alive, AnchoredLivePosition, 0f, null);
					case LiveSourceOccupancy.Dead:
						return new MarkerLiveRenderState(
							RequiresZoneReentry ? MarkerLiveStatus.ZoneReentry : AnchoredLivePosition.HasValue ? MarkerLiveStatus.DeadWithCorpse : MarkerLiveStatus.DeadNoCorpse,
							AnchoredLivePosition,
							RespawnSeconds,
							null);
					case LiveSourceOccupancy.NightLocked:
						return new MarkerLiveRenderState(MarkerLiveStatus.NightLocked, null, 0f, null);
					case LiveSourceOccupancy.UnlockBlocked:
						return new MarkerLiveRenderState(MarkerLiveStatus.UnlockBlocked, null, 0f, UnlockReason);
					default:
						return MarkerLiveRenderState.Unknown;
				}
			case LiveSourceKind.MiningNode:
				switch (Occupancy)
				{
					case LiveSourceOccupancy.Available:
						return new MarkerLiveRenderState(MarkerLiveStatus.MiningAvailable, null, 0f, null);
					case LiveSourceOccupancy.Mined:
						return new MarkerLiveRenderState(MarkerLiveStatus.MiningMined, null, RespawnSeconds, null);
					default:
						return MarkerLiveRenderState.Unknown;
				}
			case LiveSourceKind.ItemBag:
				switch (Occupancy)
				{
					case LiveSourceOccupancy.Available:
						return new MarkerLiveRenderState(MarkerLiveStatus.Alive, null, 0f, null);
					case LiveSourceOccupancy.PickedUp:
						return new MarkerLiveRenderState(MarkerLiveStatus.PickedUp, null, RespawnSeconds, null);
					default:
						return MarkerLiveRenderState.Unknown;
				}
			default:
				return MarkerLiveRenderState.Unknown;
		}
	}

	public bool Equals(LiveSourceSnapshot other) =>
		SourceNodeKey == other.SourceNodeKey
		&& TargetNodeKey == other.TargetNodeKey
		&& Kind == other.Kind
		&& Occupancy == other.Occupancy
		&& IsActionable == other.IsActionable
		&& Anchor == other.Anchor
		&& Nullable.Equals(LivePosition, other.LivePosition)
		&& Nullable.Equals(AnchoredLivePosition, other.AnchoredLivePosition)
		&& RespawnSeconds.Equals(other.RespawnSeconds)
		&& UnlockReason == other.UnlockReason
		&& RequiresZoneReentry == other.RequiresZoneReentry;

	public override bool Equals(object? obj) => obj is LiveSourceSnapshot other && Equals(other);

	public override int GetHashCode()
	{
		var first = HashCode.Combine(SourceNodeKey, TargetNodeKey, Kind, Occupancy, IsActionable);
		var second = HashCode.Combine(Anchor, LivePosition, AnchoredLivePosition, RespawnSeconds, UnlockReason, RequiresZoneReentry);
		return HashCode.Combine(first, second);
	}

	public static bool operator ==(LiveSourceSnapshot left, LiveSourceSnapshot right) => left.Equals(right);

	public static bool operator !=(LiveSourceSnapshot left, LiveSourceSnapshot right) => !left.Equals(right);
}

public enum LiveSourceKind : byte
{
	Unknown,
	Character,
	MiningNode,
	ItemBag,
}

public enum LiveSourceOccupancy : byte
{
	Unknown,
	Alive,
	Dead,
	Available,
	PickedUp,
	Mined,
	NightLocked,
	UnlockBlocked,
	Disabled,
}

public enum LiveSourceAnchor : byte
{
	None,
	Source,
	LiveObject,
}

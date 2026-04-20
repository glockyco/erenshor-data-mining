using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Markers;

/// <summary>
/// Reads engine-backed <see cref="MarkerCandidateList"/> values for the current
/// scene and materialises live <see cref="MarkerEntry"/> instances when the
/// candidate-list reference changes.
/// </summary>
internal sealed class MarkerProjector
{
	private const float StaticHeightOffset = 2.5f;

	private readonly GuideReader _reader;
	private readonly IMarkerLiveStateProvider _liveState;
	private readonly CompiledGuideModel _guide;
	private readonly DiagnosticsCore? _diagnostics;

	private MarkerCandidateList? _lastCandidates;
	private readonly List<MarkerEntry> _entries = new();
	private long _lastProjectionTicks;

	public IReadOnlyList<MarkerEntry> Markers => _entries;
	public MarkerCandidateList? LastCandidates => _lastCandidates;

	public MarkerProjector(
		GuideReader reader,
		IMarkerLiveStateProvider liveState,
		CompiledGuideModel guide,
		DiagnosticsCore? diagnostics = null)
	{
		_reader = reader;
		_liveState = liveState;
		_guide = guide;
		_diagnostics = diagnostics;
	}

	/// <summary>Reads <see cref="MarkerCandidateList"/> through the engine. When
	/// the candidate-list reference changes, rebuilds the entry list and binds live
	/// game-object references for per-frame rendering.</summary>
	public void Project()
	{
		using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.MarkerProjectorProject);

		var candidates = _reader.ReadMarkerCandidates(_reader.CurrentScene);
		if (ReferenceEquals(candidates, _lastCandidates))
			return;

		long start = Stopwatch.GetTimestamp();
		_entries.Clear();
		foreach (var candidate in candidates.Candidates)
			_entries.Add(BuildEntry(candidate));
		_lastCandidates = candidates;
		_lastProjectionTicks = Stopwatch.GetTimestamp() - start;
	}

	private MarkerEntry BuildEntry(MarkerCandidate candidate)
	{
		var entry = new MarkerEntry(candidate)
		{
			Y = candidate.Y + StaticHeightOffset,
		};

		string basePositionKey = candidate.IsSpawnTimerSlot
			? candidate.SourceNodeKey ?? candidate.PositionNodeKey
			: candidate.PositionNodeKey;
		var positionNode = _guide.GetNode(basePositionKey)
			?? throw new InvalidOperationException($"Marker position node '{basePositionKey}' was not found.");
		var targetNode = _guide.GetNode(candidate.TargetNodeKey)
			?? throw new InvalidOperationException($"Marker target node '{candidate.TargetNodeKey}' was not found.");

		SpawnInfo? spawnInfo = null;
		if (positionNode.Type == NodeType.SpawnPoint || positionNode.IsDirectlyPlaced)
		{
			var info = _liveState.GetSpawnState(positionNode);
			entry.LiveSpawnPoint = info.LiveSpawnPoint;
			entry.TrackedNPC = info.LiveNPC;
			spawnInfo = info;
		}
		else if (targetNode.Type == NodeType.Character)
		{
			var info = _liveState.GetCharacterState(targetNode);
			entry.TrackedNPC = info.LiveNPC;
			spawnInfo = info;
		}

		if (targetNode.Type == NodeType.MiningNode)
			entry.LiveMiningNode = _liveState.GetMiningState(targetNode).LiveNode;

		if (candidate.IsSpawnTimerSlot)
		{
			if (positionNode.IsDirectlyPlaced && entry.LiveSpawnPoint == null)
			{
				entry.Type = MarkerType.ZoneReentry;
				entry.Priority = 0;
				entry.SubText = $"{candidate.DisplayName}\nRe-enter zone";
			}
			else
			{
				entry.Type = MarkerType.DeadSpawn;
				entry.Priority = 0;
				entry.SubText = string.Empty;
			}
			return entry;
		}

		if (targetNode.Type == NodeType.ItemBag)
		{
			var bagState = _liveState.GetItemBagState(targetNode);
			if (bagState is ItemBagPickedUp)
			{
				entry.Type = MarkerType.ZoneReentry;
				entry.Priority = 0;
				entry.SubText = $"{candidate.DisplayName}\nRe-enter zone";
				return entry;
			}
		}

		if (targetNode.Type == NodeType.MiningNode)
		{
			var mining = _liveState.GetMiningState(targetNode);
			if (mining.State is MiningMined)
			{
				entry.Type = MarkerType.DeadSpawn;
				entry.Priority = 0;
				entry.SubText = string.Empty;
				return entry;
			}
		}

		switch (candidate.SpawnCategory)
		{
			case SpawnCategory.Alive:
			case SpawnCategory.NotApplicable:
				entry.Type = MarkerEntry.ToMarkerType(candidate.QuestKind);
				entry.Priority = candidate.Priority;
				entry.SubText = candidate.SubText;
				break;
			case SpawnCategory.Dead:
				entry.Type = MarkerType.DeadSpawn;
				entry.Priority = 0;
				entry.SubText = string.Empty;
				break;
			case SpawnCategory.NightLocked:
				entry.Type = MarkerType.NightSpawn;
				entry.Priority = 0;
				entry.SubText = BuildNightLockedText(candidate.DisplayName);
				break;
			case SpawnCategory.UnlockBlocked:
				entry.Type = MarkerType.QuestLocked;
				entry.Priority = 0;
				entry.SubText = $"{candidate.DisplayName}\n{candidate.UnlockBlockedReason ?? string.Empty}";
				break;
			case SpawnCategory.Disabled:
				entry.Type = MarkerEntry.ToMarkerType(candidate.QuestKind);
				entry.Priority = candidate.Priority;
				entry.SubText = candidate.SubText;
				break;
			default:
				throw new ArgumentOutOfRangeException();
		}

		if (spawnInfo is { State: SpawnUnlockBlocked blocked } && candidate.SpawnCategory == SpawnCategory.UnlockBlocked)
			entry.SubText = $"{candidate.DisplayName}\n{blocked.Reason}";

		return entry;
	}

	private static string BuildNightLockedText(string displayName)
	{
		int hour = GameData.Time.GetHour();
		int min = GameData.Time.min;
		return $"{displayName}\nNight only (23:00-04:00)\nNow: {hour}:{min:D2}";
	}

	internal MarkerDiagnosticsSnapshot ExportDiagnosticsSnapshot()
	{
		return new MarkerDiagnosticsSnapshot(
			candidateCount: _lastCandidates?.Candidates.Count ?? 0,
			entryCount: _entries.Count,
			lastProjectionTicks: _lastProjectionTicks
		);
	}

	internal IReadOnlyCollection<string>? GetContributingQuestKeys(string positionNodeKey)
	{
		if (_lastCandidates == null)
			return null;

		HashSet<string>? bucket = null;
		foreach (var candidate in _lastCandidates.Candidates)
		{
			if (candidate.PositionNodeKey == positionNodeKey)
				(bucket ??= new HashSet<string>(StringComparer.Ordinal)).Add(candidate.QuestKey);
		}
		return bucket;
	}
}

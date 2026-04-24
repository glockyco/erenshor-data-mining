using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Markers.Queries;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Markers;

internal interface IMarkerProjection
{
	IReadOnlyList<MarkerEntry> Markers { get; }
	MarkerCandidateList? LastCandidates { get; }
}

/// <summary>
/// Reads engine-backed <see cref="MarkerCandidateList"/> values for the current
/// scene and materialises <see cref="MarkerEntry"/> instances. Static entries are
/// rebuilt only when the candidate-list reference changes; per-frame live-state
/// overlays are applied on every projection.
/// </summary>
internal sealed class MarkerProjector : IMarkerProjection
{
	private const float StaticHeightOffset = 2.5f;

	private readonly GuideReader _reader;
	private readonly MarkerCandidatesQuery _markerCandidatesQuery;
	private readonly ILiveSourceSnapshotProvider _liveState;
	private readonly CompiledGuideModel _guide;
	private readonly DiagnosticsCore? _diagnostics;

	private MarkerCandidateList? _lastCandidates;
	private readonly List<MarkerEntry> _entries = new();
	private readonly List<MarkerEntry> _projectedEntries = new();
	private long _lastProjectionTicks;

	public IReadOnlyList<MarkerEntry> Markers => _projectedEntries;
	public MarkerCandidateList? LastCandidates => _lastCandidates;

	public MarkerProjector(
		GuideReader reader,
		MarkerCandidatesQuery markerCandidatesQuery,
		ILiveSourceSnapshotProvider liveState,
		CompiledGuideModel guide,
		DiagnosticsCore? diagnostics = null)
	{
		_reader = reader;
		_markerCandidatesQuery = markerCandidatesQuery;
		_liveState = liveState;
		_guide = guide;
		_diagnostics = diagnostics;
	}

	public void Project()
	{
		using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.MarkerProjectorProject);

		var candidates = _reader.Engine.Read(_markerCandidatesQuery.Query, _reader.CurrentScene);
		long start = Stopwatch.GetTimestamp();

		if (!ReferenceEquals(candidates, _lastCandidates))
			RebuildEntries(candidates);

		for (int i = 0; i < _entries.Count; i++)
			ApplyLiveRenderState(_entries[i]);

		BuildProjectedEntries();
		_lastProjectionTicks = Stopwatch.GetTimestamp() - start;
	}

	private void RebuildEntries(MarkerCandidateList candidates)
	{
		_entries.Clear();
		_lastCandidates = candidates;

		var selectedCandidates = new Dictionary<string, MarkerCandidate>(StringComparer.Ordinal);
		foreach (var candidate in candidates.Candidates)
		{
			string dedupeKey = BuildRenderDedupeKey(candidate);
			if (!selectedCandidates.TryGetValue(dedupeKey, out var existing)
				|| candidate.Priority > existing.Priority)
			{
				selectedCandidates[dedupeKey] = candidate;
			}
		}

		foreach (var candidate in selectedCandidates.Values
			.OrderBy(candidate => candidate.Priority)
			.ThenBy(candidate => candidate.PositionNodeKey, StringComparer.Ordinal))
		{
			_entries.Add(new MarkerEntry(candidate)
			{
				Y = candidate.Y + StaticHeightOffset,
				Type = MarkerEntry.ToMarkerType(candidate.QuestKind),
				Priority = candidate.Priority,
				SubText = candidate.SubText,
			});
		}
	}

	private LiveSourceSnapshot GetLiveSourceSnapshot(MarkerCandidate candidate)
	{
		var sourceNodeKey = candidate.SourceNodeKey ?? candidate.PositionNodeKey;
		var positionNode = _guide.GetNode(candidate.PositionNodeKey);
		if (positionNode == null)
			return LiveSourceSnapshot.Unknown(sourceNodeKey, candidate.TargetNodeKey);

		var targetNode = _guide.GetNode(candidate.TargetNodeKey);
		if (targetNode == null)
			return LiveSourceSnapshot.Unknown(sourceNodeKey, candidate.TargetNodeKey);

		return _liveState.GetLiveSourceSnapshot(sourceNodeKey, positionNode, targetNode);
	}

	private static MarkerLiveRenderState ToMarkerRenderState(LiveSourceSnapshot snapshot)
	{
		switch (snapshot.Kind)
		{
			case LiveSourceKind.Character:
				switch (snapshot.Occupancy)
				{
					case LiveSourceOccupancy.Alive:
						return new MarkerLiveRenderState(MarkerLiveStatus.Alive, snapshot.AnchoredLivePosition, 0f, null);
					case LiveSourceOccupancy.Dead:
						return new MarkerLiveRenderState(
							snapshot.RequiresZoneReentry
								? MarkerLiveStatus.ZoneReentry
								: snapshot.AnchoredLivePosition.HasValue
									? MarkerLiveStatus.DeadWithCorpse
									: MarkerLiveStatus.DeadNoCorpse,
							snapshot.AnchoredLivePosition,
							snapshot.RespawnSeconds,
							null);
					case LiveSourceOccupancy.NightLocked:
						return new MarkerLiveRenderState(MarkerLiveStatus.NightLocked, null, 0f, null);
					case LiveSourceOccupancy.UnlockBlocked:
						return new MarkerLiveRenderState(MarkerLiveStatus.UnlockBlocked, null, 0f, snapshot.UnlockReason);
					case LiveSourceOccupancy.Disabled:
						return new MarkerLiveRenderState(MarkerLiveStatus.Disabled, null, 0f, null);
					default:
						return MarkerLiveRenderState.Unknown;
				}
			case LiveSourceKind.MiningNode:
				switch (snapshot.Occupancy)
				{
					case LiveSourceOccupancy.Available:
						return new MarkerLiveRenderState(MarkerLiveStatus.MiningAvailable, null, 0f, null);
					case LiveSourceOccupancy.Mined:
						return new MarkerLiveRenderState(MarkerLiveStatus.MiningMined, null, snapshot.RespawnSeconds, null);
					default:
						return MarkerLiveRenderState.Unknown;
				}
			case LiveSourceKind.ItemBag:
				switch (snapshot.Occupancy)
				{
					case LiveSourceOccupancy.Available:
						return new MarkerLiveRenderState(MarkerLiveStatus.Alive, null, 0f, null);
					case LiveSourceOccupancy.PickedUp:
						return new MarkerLiveRenderState(MarkerLiveStatus.PickedUp, null, snapshot.RespawnSeconds, null);
					default:
						return MarkerLiveRenderState.Unknown;
				}
			default:
				return MarkerLiveRenderState.Unknown;
		}
	}

	private void ApplyLiveRenderState(MarkerEntry entry)
	{
		var candidate = entry.Candidate;
		var state = ToMarkerRenderState(GetLiveSourceSnapshot(candidate));

		switch (state.Status)
		{
			case MarkerLiveStatus.Alive:
				entry.Type = MarkerEntry.ToMarkerType(candidate.QuestKind);
				entry.Priority = candidate.Priority;
				entry.SubText = candidate.SubText;
				ApplyPosition(entry, state.LivePosition);
				break;

			case MarkerLiveStatus.DeadWithCorpse:
				entry.Type = MarkerType.DeadSpawn;
				entry.Priority = 0;
				entry.SubText = $"{entry.DisplayName}\n{FormatTimer(state.RespawnSeconds)}";
				ApplyPosition(entry, state.LivePosition);
				break;

			case MarkerLiveStatus.DeadNoCorpse:
				entry.Type = MarkerType.DeadSpawn;
				entry.Priority = 0;
				entry.SubText = $"{entry.DisplayName}\n{FormatTimer(state.RespawnSeconds)}";
				ApplyStaticPosition(entry);
				break;

			case MarkerLiveStatus.NightLocked:
				entry.Type = MarkerType.NightSpawn;
				entry.Priority = 0;
				entry.SubText = BuildNightLockedText(entry.DisplayName);
				ApplyStaticPosition(entry);
				break;

			case MarkerLiveStatus.UnlockBlocked:
			    entry.Type = MarkerType.QuestLocked;
			    entry.Priority = 0;
			    entry.SubText = $"{entry.DisplayName}\n{state.UnlockReason ?? string.Empty}";
			    ApplyStaticPosition(entry);
			    break;

			case MarkerLiveStatus.Disabled:
			    entry.Type = MarkerType.QuestLocked;
			    entry.Priority = 0;
			    entry.SubText = $"{entry.DisplayName}\nDisabled";
			    ApplyStaticPosition(entry);
			    break;

			case MarkerLiveStatus.PickedUp:
			case MarkerLiveStatus.ZoneReentry:
				entry.Type = MarkerType.ZoneReentry;
				entry.Priority = 0;
				entry.SubText = $"{candidate.DisplayName}\nRe-enter zone";
				ApplyStaticPosition(entry);
				break;

			case MarkerLiveStatus.MiningAvailable:
				entry.Type = MarkerEntry.ToMarkerType(candidate.QuestKind);
				entry.Priority = candidate.Priority;
				entry.SubText = candidate.SubText;
				ApplyStaticPosition(entry);
				break;

			case MarkerLiveStatus.MiningMined:
				entry.Type = MarkerType.DeadSpawn;
				entry.Priority = 0;
				entry.SubText = $"{entry.DisplayName}\n{FormatTimer(state.RespawnSeconds)}";
				ApplyStaticPosition(entry);
				break;

			case MarkerLiveStatus.Unknown:
			default:
				entry.Type = MarkerEntry.ToMarkerType(candidate.QuestKind);
				entry.Priority = candidate.Priority;
				entry.SubText = candidate.SubText;
				ApplyStaticPosition(entry);
				break;
		}
	}

	private static void ApplyPosition(MarkerEntry entry, (float X, float Y, float Z)? livePos)
	{
		if (livePos is { } p)
		{
			entry.X = p.X;
			entry.Y = p.Y;
			entry.Z = p.Z;
		}
		else
		{
			ApplyStaticPosition(entry);
		}
	}

	private static void ApplyStaticPosition(MarkerEntry entry)
	{
		entry.X = entry.Candidate.X;
		entry.Y = entry.Candidate.Y + StaticHeightOffset;
		entry.Z = entry.Candidate.Z;
	}

	private void BuildProjectedEntries()
	{
		_projectedEntries.Clear();

		var seenKeys = new HashSet<string>(StringComparer.Ordinal);
		for (int i = 0; i < _entries.Count; i++)
		{
			var entry = _entries[i];
			if (RequiresSourceUniqueLifecycleDedupe(entry)
				&& !seenKeys.Add(BuildLifecycleDedupeKey(entry)))
			{
				continue;
			}

			_projectedEntries.Add(entry);
		}
	}

	internal void InvalidateProjection()
	{
		_lastCandidates = null;
		_entries.Clear();
		_projectedEntries.Clear();
	}

	private static bool RequiresSourceUniqueLifecycleDedupe(MarkerEntry entry) =>
		entry.Type is MarkerType.DeadSpawn or MarkerType.ZoneReentry or MarkerType.QuestLocked;

	private static string BuildLifecycleDedupeKey(MarkerEntry entry) =>
		string.Join("|", new[]
		{
			entry.Scene,
			entry.SourceKey,
			entry.Type.ToString(),
		});

	private static string BuildRenderDedupeKey(MarkerCandidate candidate) =>
		string.Join("|", new[]
		{
			candidate.Scene,
			candidate.SourceNodeKey ?? candidate.PositionNodeKey,
			candidate.QuestKind.ToString(),
		});

	private static string BuildNightLockedText(string displayName)
	{
		int hour = GameData.Time.GetHour();
		int min = GameData.Time.min;
		return $"{displayName}\nNight only (23:00-04:00)\nNow: {hour}:{min:D2}";
	}

	private static string FormatTimer(float seconds)
	{
		if (seconds <= 0f)
			return "Respawning...";
		int totalSeconds = (int)seconds;
		int minutes = totalSeconds / 60;
		int remainingSeconds = totalSeconds % 60;
		return $"~{minutes}:{remainingSeconds:D2}";
	}

	internal MarkerDiagnosticsSnapshot ExportDiagnosticsSnapshot()
	{
		return new MarkerDiagnosticsSnapshot(
			candidateCount: _lastCandidates?.Candidates.Count ?? 0,
			entryCount: _entries.Count,
			lastProjectionTicks: _lastProjectionTicks);
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

using AdventureGuide.Config;
using UnityEngine;

namespace AdventureGuide.Markers;

/// <summary>
/// Renders world-space billboard markers from <see cref="MarkerProjector"/>
/// output using <see cref="MarkerPool"/>.
/// </summary>
public sealed class MarkerRenderer
{
	private const float StaticHeightOffset = 2.5f;
	private const float LiveHeightAboveCollider = 0.8f;

	private readonly MarkerProjector _projector;
	private readonly MarkerPool _pool;
	private readonly GuideConfig _config;

	private bool _enabled;
	private bool _configDirty;
	private string _currentScene = "";
	private MarkerCandidateList? _lastConfiguredCandidates;

	public bool Enabled
	{
		get => _enabled;
		set
		{
			if (_enabled == value)
				return;
			_enabled = value;
			if (!value)
				_pool.DeactivateAll();
		}
	}

	public MarkerRenderer(MarkerProjector projector, MarkerPool pool, GuideConfig config)
	{
		_projector = projector;
		_pool = pool;
		_config = config;

		config.MarkerScale.SettingChanged += OnConfigChanged;
		config.IconSize.SettingChanged += OnConfigChanged;
		config.SubTextSize.SettingChanged += OnConfigChanged;
		config.IconYOffset.SettingChanged += OnConfigChanged;
		config.SubTextYOffset.SettingChanged += OnConfigChanged;
	}

	/// <summary>Per-frame render. Reconfigures the pool when the projector's
	/// candidate-list reference changes; otherwise updates live per-frame state.
	/// </summary>
	public void Render()
	{
		if (!_enabled || GameData.PlayerControl == null || !MarkerFonts.IsReady)
			return;

		var entries = _projector.Markers;
		var candidates = _projector.LastCandidates;
		if (!ReferenceEquals(candidates, _lastConfiguredCandidates) || _configDirty)
		{
			ConfigureMarkers(entries);
			_lastConfiguredCandidates = candidates;
			_configDirty = false;
		}

		UpdateLiveState(entries);
	}

	public void OnSceneChanged(string scene)
	{
		_currentScene = scene;
		_pool.DeactivateAll();
		_lastConfiguredCandidates = null;
	}

	public void Destroy()
	{
		_config.MarkerScale.SettingChanged -= OnConfigChanged;
		_config.IconSize.SettingChanged -= OnConfigChanged;
		_config.SubTextSize.SettingChanged -= OnConfigChanged;
		_config.IconYOffset.SettingChanged -= OnConfigChanged;
		_config.SubTextYOffset.SettingChanged -= OnConfigChanged;
		_pool.Destroy();
	}

	private void OnConfigChanged(object sender, System.EventArgs e) => _configDirty = true;

	private void ConfigureMarkers(IReadOnlyList<MarkerEntry> markers)
	{
		_pool.SetActiveCount(markers.Count);
		for (int i = 0; i < markers.Count; i++)
		{
			var entry = markers[i];
			var instance = _pool.Get(i);
			instance.Configure(
				entry.Type,
				entry.SubText,
				_config.MarkerScale.Value,
				_config.IconSize.Value,
				_config.SubTextSize.Value,
				_config.IconYOffset.Value,
				_config.SubTextYOffset.Value
			);
			instance.SetActive(true);
		}
	}

	private void UpdateLiveState(IReadOnlyList<MarkerEntry> markers)
	{
		var playerPos = GameData.PlayerControl!.transform.position;

		for (int i = 0; i < markers.Count; i++)
		{
			var entry = markers[i];
			var instance = _pool.Get(i);

			if (!string.Equals(entry.Scene, _currentScene, System.StringComparison.OrdinalIgnoreCase))
			{
				instance.SetActive(false);
				continue;
			}

			bool active = true;
			if (entry.LiveMiningNode != null)
			{
				UpdateMiningState(entry, instance);
			}
			else if (entry.LiveSpawnPoint != null)
			{
				active = entry.IsSpawnTimerSlot
					? UpdateSpawnTimerState(entry, instance)
					: UpdateSpawnState(entry, instance);
			}

			if (!active)
			{
				instance.SetActive(false);
				continue;
			}

			if (entry.IsLootChestTarget)
			{
				if (entry.LiveRotChest != null && entry.LiveRotChest.gameObject == null)
				{
					instance.SetActive(false);
					continue;
				}
			}
			else if (!entry.IsSpawnTimerSlot)
			{
				UpdatePosition(entry);
			}

			var pos = new Vector3(entry.X, entry.Y, entry.Z);
			instance.SetPosition(pos);

			float dist = Vector3.Distance(playerPos, pos);
			instance.SetAlpha(dist);
			instance.SetActive(true);
		}
	}

	private bool UpdateSpawnState(MarkerEntry entry, MarkerInstance instance)
	{
		var sp = entry.LiveSpawnPoint!;
		var candidate = entry.Candidate;

		MarkerType newType;
		int newPriority;
		string newSubText;

		if (sp.NightSpawn && !IsNight())
		{
			newType = MarkerType.NightSpawn;
			newPriority = 0;
			int hour = GameData.Time.GetHour();
			int min = GameData.Time.min;
			newSubText = $"{entry.DisplayName}\nNight only (23:00-04:00)\nNow: {hour}:{min:D2}";
		}
		else if (IsSpawnedNPCAlive(sp))
		{
			newType = MarkerEntry.ToMarkerType(candidate.QuestKind);
			newPriority = candidate.Priority;
			newSubText = candidate.SubText;
		}
		else if (candidate.KeepWhileCorpsePresent && IsSpawnedNPCCorpsePresent(sp))
		{
			newType = MarkerEntry.ToMarkerType(candidate.QuestKind);
			newPriority = candidate.Priority;
			newSubText = candidate.CorpseSubText ?? candidate.SubText;
		}
		else
		{
			return false;
		}

		if (
			newType != entry.Type
			|| newPriority != entry.Priority
			|| !string.Equals(newSubText, entry.SubText, System.StringComparison.Ordinal)
		)
		{
			entry.Type = newType;
			entry.Priority = newPriority;
			entry.SubText = newSubText;
			ReconfigureInstance(entry, instance);

			if (newType == MarkerEntry.ToMarkerType(candidate.QuestKind) && sp.SpawnedNPC != null)
				SetPositionFromNPC(entry, sp.SpawnedNPC);
		}
		else if (newType == MarkerType.NightSpawn)
		{
			entry.SubText = newSubText;
			instance.UpdateSubText(newSubText);
		}

		return true;
	}

	private bool UpdateSpawnTimerState(MarkerEntry entry, MarkerInstance instance)
	{
		var sp = entry.LiveSpawnPoint!;
		if (IsSpawnedNPCAlive(sp))
			return false;

		string newSubText = FormatDeadSubText(entry.DisplayName, sp);
		if (
			entry.Type != MarkerType.DeadSpawn
			|| !string.Equals(entry.SubText, newSubText, System.StringComparison.Ordinal)
		)
		{
			entry.Type = MarkerType.DeadSpawn;
			entry.Priority = 0;
			entry.SubText = newSubText;
			ReconfigureInstance(entry, instance);
		}
		else
		{
			entry.SubText = newSubText;
			instance.UpdateSubText(newSubText);
		}

		return true;
	}

	private static bool IsSpawnedNPCAlive(SpawnPoint sp)
	{
		return sp.SpawnedNPC != null
			&& sp.SpawnedNPC.gameObject != null
			&& sp.SpawnedNPC.GetChar() != null
			&& sp.SpawnedNPC.GetChar().Alive;
	}

	private static bool IsSpawnedNPCCorpsePresent(SpawnPoint sp) =>
		sp.SpawnedNPC != null
		&& sp.SpawnedNPC.gameObject != null
		&& sp.SpawnedNPC.GetChar() != null
		&& !sp.SpawnedNPC.GetChar().Alive;

	private static bool IsNight()
	{
		int hour = GameData.Time.GetHour();
		return hour >= 22 || hour < 4;
	}

	private void UpdateMiningState(MarkerEntry entry, MarkerInstance instance)
	{
		var mn = entry.LiveMiningNode!;
		bool isMined = mn.MyRender != null && !mn.MyRender.enabled;

		if (!isMined && entry.Type != MarkerEntry.ToMarkerType(entry.Candidate.QuestKind))
		{
			entry.Type = MarkerEntry.ToMarkerType(entry.Candidate.QuestKind);
			entry.Priority = entry.Candidate.Priority;
			entry.SubText = entry.Candidate.SubText;
			ReconfigureInstance(entry, instance);
		}
		else if (isMined && entry.Type == MarkerEntry.ToMarkerType(entry.Candidate.QuestKind))
		{
			entry.Type = MarkerType.DeadSpawn;
			entry.Priority = 0;
			float seconds = GetMiningRespawnSeconds(mn);
			entry.SubText = $"{entry.DisplayName}\n{FormatTimer(seconds)}";
			ReconfigureInstance(entry, instance);
		}
		else if (isMined && entry.Type == MarkerType.DeadSpawn)
		{
			float seconds = GetMiningRespawnSeconds(mn);
			entry.SubText = $"{entry.DisplayName}\n{FormatTimer(seconds)}";
			instance.UpdateSubText(entry.SubText);
		}
	}

	private static void UpdatePosition(MarkerEntry entry)
	{
		NPC? npc = entry.LiveSpawnPoint?.SpawnedNPC ?? entry.TrackedNPC;
		if (npc == null || npc.gameObject == null)
			return;

		if (entry.IsSpawnTimerSlot || entry.Type != MarkerEntry.ToMarkerType(entry.Candidate.QuestKind))
			return;

		SetPositionFromNPC(entry, npc);
	}

	private static void SetPositionFromNPC(MarkerEntry entry, NPC npc)
	{
		var collider = npc.GetComponent<CapsuleCollider>();
		float height =
			collider != null
				? collider.height * Mathf.Max(npc.transform.localScale.y, 1f) + LiveHeightAboveCollider
				: StaticHeightOffset;
		var pos = npc.transform.position + Vector3.up * height;
		entry.X = pos.x;
		entry.Y = pos.y;
		entry.Z = pos.z;
	}

	private void ReconfigureInstance(MarkerEntry entry, MarkerInstance instance)
	{
		instance.Configure(
			entry.Type,
			entry.SubText,
			_config.MarkerScale.Value,
			_config.IconSize.Value,
			_config.SubTextSize.Value,
			_config.IconYOffset.Value,
			_config.SubTextYOffset.Value
		);
	}

	private static string FormatDeadSubText(string displayName, SpawnPoint sp)
	{
		float spawnTimeMod = GameData.GM != null ? GameData.GM.SpawnTimeMod : 1f;
		float tickRate = 60f * spawnTimeMod;
		float seconds = tickRate > 0f ? sp.actualSpawnDelay / tickRate : 0f;
		return $"{displayName}\n{FormatTimer(seconds)}";
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

	private static readonly System.Reflection.FieldInfo? MiningRespawnField =
		typeof(MiningNode).GetField(
			"Respawn",
			System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic
		);

	private static float GetMiningRespawnSeconds(MiningNode mn)
	{
		if (MiningRespawnField == null)
			return 0f;
		object? val = MiningRespawnField.GetValue(mn);
		if (val is float ticks)
			return ticks / 60f;
		return 0f;
	}
}

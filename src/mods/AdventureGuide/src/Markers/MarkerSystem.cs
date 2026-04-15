using AdventureGuide.Config;
using UnityEngine;

namespace AdventureGuide.Markers;

/// <summary>
/// Renders world-space billboard markers from <see cref="MarkerComputer"/> output
/// using <see cref="MarkerPool"/>. Each frame:
/// 1. If MarkerComputer version changed or config dirty, re-configure pool from markers.
/// 2. Per-frame: detect alive/dead transitions, update timer text, track live NPC
///    positions, apply distance-based alpha fading.
/// </summary>
public sealed class MarkerSystem
{
    private const float StaticHeightOffset = 2.5f;
    private const float LiveHeightAboveCollider = 0.8f;

    private readonly MarkerComputer _computer;
    private readonly MarkerPool _pool;
    private readonly GuideConfig _config;

    private bool _enabled;
    private bool _configDirty;
    private string _currentScene = "";
    private int _lastConfiguredVersion = -1;

    public bool Enabled
    {
        get => _enabled;
        set
        {
            if (_enabled == value) return;
            _enabled = value;
            if (!value) _pool.DeactivateAll();
        }
    }

    public MarkerSystem(MarkerComputer computer, MarkerPool pool, GuideConfig config)
    {
        _computer = computer;
        _pool = pool;
        _config = config;

        config.MarkerScale.SettingChanged += OnConfigChanged;
        config.IconSize.SettingChanged += OnConfigChanged;
        config.SubTextSize.SettingChanged += OnConfigChanged;
        config.IconYOffset.SettingChanged += OnConfigChanged;
        config.SubTextYOffset.SettingChanged += OnConfigChanged;
    }

    /// <summary>Update marker rendering. Call each frame from Plugin.Update.</summary>
    public void Update()
    {
        if (!_enabled || GameData.PlayerControl == null || !MarkerFonts.IsReady)
            return;

        var markers = _computer.Markers;

        // Re-configure pool when marker set or config changed
        if (_computer.Version != _lastConfiguredVersion || _configDirty)
        {
            ConfigureMarkers(markers);
            _lastConfiguredVersion = _computer.Version;
            _configDirty = false;
        }

        // Per-frame: state transitions, timers, position tracking, distance fading
        UpdateLiveState(markers);
    }

    /// <summary>Call on scene change to deactivate stale markers.</summary>
    public void OnSceneChanged(string scene)
    {
        _currentScene = scene;
        _pool.DeactivateAll();
        _lastConfiguredVersion = -1;
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

    /// <summary>Configure all pool instances from the marker list.</summary>
    private void ConfigureMarkers(IReadOnlyList<MarkerEntry> markers)
    {
        _pool.SetActiveCount(markers.Count);
        for (int i = 0; i < markers.Count; i++)
        {
            var entry = markers[i];
            var instance = _pool.Get(i);
            instance.Configure(
                entry.Type, entry.SubText,
                _config.MarkerScale.Value, _config.IconSize.Value,
                _config.SubTextSize.Value, _config.IconYOffset.Value,
                _config.SubTextYOffset.Value);
            instance.SetActive(true);
        }
    }

    /// <summary>
    /// Per-frame update: detect alive/dead transitions on spawn-based markers,
    /// update respawn timer text, track live NPC positions, apply distance fading.
    /// </summary>
    private void UpdateLiveState(IReadOnlyList<MarkerEntry> markers)
    {
        var playerPos = GameData.PlayerControl!.transform.position;

        for (int i = 0; i < markers.Count; i++)
        {
            var entry = markers[i];
            var instance = _pool.Get(i);

            // Only render markers in the current scene
            if (!string.Equals(entry.Scene, _currentScene,
                    System.StringComparison.OrdinalIgnoreCase))
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
                active = entry.IsSpawnTimer
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
                // Hide when the chest has rotted away (gameObject destroyed by RotChest.FixedUpdate).
                if (entry.LiveRotChest != null && entry.LiveRotChest.gameObject == null)
                {
                    instance.SetActive(false);
                    continue;
                }
                // Chest position is static — fall through to distance fading without UpdatePosition.
            }
            else if (!entry.IsSpawnTimer)
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

    /// <summary>
    /// Per-frame state update for spawn-point-based active markers.
    ///
    /// Handles transitions that occur without quest state changes:
    ///   - Alive ↔ Dead (NPC killed / respawned)
    ///   - Night ↔ Day (NightSpawn NPCs appear/disappear with time)
    ///   - Night time display updates
    ///
    /// When the NPC dies and the entry has no corpse loot tracking
    /// (KeepWhileCorpsePresent), returns false to hide the active marker.
    /// The respawn-timer marker handles dead/empty display.
    ///
    /// canSpawn changes (quest gates, StopIfQuestComplete) trigger
    /// MarkerComputer.MarkDirty via patches, so a full recompute handles
    /// those before the next MarkerSystem.Update.
    ///
    /// Uses SpawnedNPC.GetChar().Alive instead of sp.MyNPCAlive, which
    /// the game sets on spawn but never clears on death.
    /// </summary>
    private bool UpdateSpawnState(MarkerEntry entry, MarkerInstance instance)
    {
        var sp = entry.LiveSpawnPoint!;

        MarkerType newType;
        int newPriority;
        string newSubText;

        if (sp.NightSpawn && !IsNight())
        {
            // Night-only spawn during daytime — NPC doesn't exist
            newType = MarkerType.NightSpawn;
            newPriority = 0;
            int hour = GameData.Time.GetHour();
            int min = GameData.Time.min;
            newSubText = $"{entry.DisplayName}\nNight only (23:00-04:00)\nNow: {hour}:{min:D2}";
        }
        else if (IsSpawnedNPCAlive(sp))
        {
            newType = MarkerEntry.ToMarkerType(entry.QuestKind!.Value);
            newPriority = entry.QuestPriority;
            newSubText = entry.QuestSubText;
        }
        else if (entry.KeepWhileCorpsePresent && IsSpawnedNPCCorpsePresent(sp))
        {
            newType = MarkerEntry.ToMarkerType(entry.QuestKind!.Value);
            newPriority = entry.QuestPriority;
            newSubText = entry.CorpseSubText ?? entry.QuestSubText;
        }
        else
        {
            // Dead or not yet spawned — hide active marker; respawn timer handles display
            return false;
        }

        if (newType != entry.Type
            || newPriority != entry.Priority
            || !string.Equals(newSubText, entry.SubText, System.StringComparison.Ordinal))
        {
            entry.Type = newType;
            entry.Priority = newPriority;
            entry.SubText = newSubText;
            ReconfigureInstance(entry, instance);

            if (newType == MarkerEntry.ToMarkerType(entry.QuestKind!.Value) && sp.SpawnedNPC != null)
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
        if (entry.Type != MarkerType.DeadSpawn || !string.Equals(entry.SubText, newSubText, System.StringComparison.Ordinal))
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

    /// <summary>
    /// Check whether a SpawnPoint's NPC is alive. Matches the game's own
    /// check in SpawnPoint.Update: SpawnedNPC != null &amp;&amp; GetChar().Alive.
    /// Do NOT use sp.MyNPCAlive — set on spawn, never cleared on death.
    /// </summary>
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

    /// <summary>
    /// Detect mined/available transitions on mining-node-based markers.
    /// </summary>
    private void UpdateMiningState(MarkerEntry entry, MarkerInstance instance)
    {
        var mn = entry.LiveMiningNode!;
        bool isMined = mn.MyRender != null && !mn.MyRender.enabled;

        if (!isMined && entry.Type != MarkerEntry.ToMarkerType(entry.QuestKind!.Value))
        {
            // Regenerated: restore quest marker
            entry.Type = MarkerEntry.ToMarkerType(entry.QuestKind!.Value);
            entry.Priority = entry.QuestPriority;
            entry.SubText = entry.QuestSubText;
            ReconfigureInstance(entry, instance);
        }
        else if (isMined && entry.Type == MarkerEntry.ToMarkerType(entry.QuestKind!.Value))
        {
            // Just mined: switch to skull with timer
            entry.Type = MarkerType.DeadSpawn;
            entry.Priority = 0;
            float seconds = GetMiningRespawnSeconds(mn);
            entry.SubText = $"{entry.DisplayName}\n{MarkerComputer.FormatTimer(seconds)}";
            ReconfigureInstance(entry, instance);
        }
        else if (isMined && entry.Type == MarkerType.DeadSpawn)
        {
            // Still mined: update timer every frame
            float seconds = GetMiningRespawnSeconds(mn);
            entry.SubText = $"{entry.DisplayName}\n{MarkerComputer.FormatTimer(seconds)}";
            instance.UpdateSubText(entry.SubText);
        }
    }

    /// <summary>
    /// Track live NPC position when alive. Reads from SpawnPoint.SpawnedNPC
    /// (spawn-based markers) or TrackedNPC (directly placed NPCs).
    /// </summary>
    private static void UpdatePosition(MarkerEntry entry)
    {
        NPC? npc = entry.LiveSpawnPoint?.SpawnedNPC ?? entry.TrackedNPC;
        if (npc == null || npc.gameObject == null) return;

        // Only track live positions for quest-type markers (not dead/night/locked)
        if (!entry.QuestKind.HasValue || entry.Type != MarkerEntry.ToMarkerType(entry.QuestKind.Value)) return;

        SetPositionFromNPC(entry, npc);
    }

    /// <summary>
    /// Set marker position from a live NPC, using CapsuleCollider height
    /// for proper placement above the NPC's head.
    /// </summary>
    private static void SetPositionFromNPC(MarkerEntry entry, NPC npc)
    {
        var collider = npc.GetComponent<CapsuleCollider>();
        float height = collider != null
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
            entry.Type, entry.SubText,
            _config.MarkerScale.Value, _config.IconSize.Value,
            _config.SubTextSize.Value, _config.IconYOffset.Value,
            _config.SubTextYOffset.Value);
    }

    private static string FormatDeadSubText(string displayName, SpawnPoint sp)
    {
        float spawnTimeMod = GameData.GM != null ? GameData.GM.SpawnTimeMod : 1f;
        float tickRate = 60f * spawnTimeMod;
        float seconds = tickRate > 0f ? sp.actualSpawnDelay / tickRate : 0f;
        return $"{displayName}\n{MarkerComputer.FormatTimer(seconds)}";
    }

    private static readonly System.Reflection.FieldInfo? MiningRespawnField =
        typeof(MiningNode).GetField("Respawn",
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);

    private static float GetMiningRespawnSeconds(MiningNode mn)
    {
        if (MiningRespawnField == null) return 0f;
        object? val = MiningRespawnField.GetValue(mn);
        if (val is float ticks) return ticks / 60f;
        return 0f;
    }
}

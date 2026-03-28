using AdventureGuide.Config;
using AdventureGuide.Navigation;
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

            // Per-frame spawn state transitions
            if (entry.LiveMiningNode != null)
                UpdateMiningState(entry, instance);
            else if (entry.LiveSpawnPoint != null)
                UpdateSpawnState(entry, instance);

            // Live NPC position tracking (alive markers with a tracked NPC)
            UpdatePosition(entry);

            var pos = new Vector3(entry.X, entry.Y, entry.Z) + Vector3.up * StaticHeightOffset;
            instance.SetPosition(pos);

            float dist = Vector3.Distance(playerPos, pos);
            instance.SetAlpha(dist);
            instance.SetActive(true);
        }
    }

    /// <summary>
    /// Detect alive/dead transitions on spawn-point-based markers and update
    /// marker type, sub-text, and position accordingly.
    /// </summary>
    private void UpdateSpawnState(MarkerEntry entry, MarkerInstance instance)
    {
        var sp = entry.LiveSpawnPoint!;
        bool isAlive = sp.MyNPCAlive;

        if (isAlive && entry.Type != entry.QuestType)
        {
            // Dead → Alive: restore quest marker
            entry.Type = entry.QuestType;
            entry.SubText = entry.QuestSubText;
            ReconfigureInstance(entry, instance);

            // Update position to the live NPC
            if (sp.SpawnedNPC != null)
                SetPositionFromNPC(entry, sp.SpawnedNPC);
        }
        else if (!isAlive && entry.Type == entry.QuestType)
        {
            // Alive → Dead: switch to skull with timer
            entry.Type = MarkerType.DeadSpawn;
            entry.SubText = FormatDeadSubText(entry.DisplayName, sp);
            ReconfigureInstance(entry, instance);
        }
        else if (entry.Type == MarkerType.DeadSpawn)
        {
            // Still dead: update timer text every frame
            entry.SubText = FormatDeadSubText(entry.DisplayName, sp);
            instance.UpdateSubText(entry.SubText);
        }
    }

    /// <summary>
    /// Detect mined/available transitions on mining-node-based markers.
    /// </summary>
    private void UpdateMiningState(MarkerEntry entry, MarkerInstance instance)
    {
        var mn = entry.LiveMiningNode!;
        bool isMined = mn.MyRender != null && !mn.MyRender.enabled;

        if (!isMined && entry.Type != entry.QuestType)
        {
            // Regenerated: restore quest marker
            entry.Type = entry.QuestType;
            entry.SubText = entry.QuestSubText;
            ReconfigureInstance(entry, instance);
        }
        else if (isMined && entry.Type == entry.QuestType)
        {
            // Just mined: switch to skull with timer
            entry.Type = MarkerType.DeadSpawn;
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
        if (entry.Type != entry.QuestType) return;

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

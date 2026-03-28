using AdventureGuide.Config;
using AdventureGuide.Navigation;
using UnityEngine;

namespace AdventureGuide.Markers;

/// <summary>
/// Renders world-space billboard markers from <see cref="MarkerComputer"/> output
/// using <see cref="MarkerPool"/>. Each frame:
/// 1. If MarkerComputer rebuilt (marker count changed or config dirty), re-configure pool.
/// 2. Update marker positions (live NPC tracking) and distance-based alpha fading.
/// 3. Update timer sub-text for dead/mined markers via <see cref="LiveStateTracker"/>.
///
/// Replaces WorldMarkerSystem. Reads computed marker data instead of doing
/// its own per-quest iteration.
/// </summary>
public sealed class MarkerSystem
{
    private const float HeightOffset = 2.5f;

    private readonly MarkerComputer _computer;
    private readonly MarkerPool _pool;
    private readonly LiveStateTracker _liveState;
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

    public MarkerSystem(MarkerComputer computer, MarkerPool pool,
        LiveStateTracker liveState, GuideConfig config)
    {
        _computer = computer;
        _pool = pool;
        _liveState = liveState;
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

        // Per-frame: position updates and distance fading
        var playerPos = GameData.PlayerControl.transform.position;
        int activeCount = 0;

        for (int i = 0; i < markers.Count; i++)
        {
            var entry = markers[i];

            // Only render markers in the current scene
            if (!string.Equals(entry.Scene, _currentScene,
                    System.StringComparison.OrdinalIgnoreCase))
            {
                _pool.Get(i).SetActive(false);
                continue;
            }

            var instance = _pool.Get(i);
            var pos = new Vector3(entry.X, entry.Y, entry.Z) + Vector3.up * HeightOffset;
            instance.SetPosition(pos);

            float dist = Vector3.Distance(playerPos, pos);
            instance.SetAlpha(dist);
            instance.SetActive(true);
            activeCount++;
        }
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

    /// <summary>
    /// Configure all pool instances from the current marker set.
    /// Handles priority dedup: when multiple markers overlap at the same
    /// position, the highest-priority marker type wins.
    /// </summary>
    private void ConfigureMarkers(IReadOnlyList<MarkerEntry> markers)
    {
        // Dedup by position: MarkerType enum values are priority-ordered
        // (lower = higher priority)
        var deduped = DeduplicateByPosition(markers);

        _pool.SetActiveCount(deduped.Count);
        for (int i = 0; i < deduped.Count; i++)
        {
            var entry = deduped[i];
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
    /// Deduplicate markers by approximate position. When multiple markers are
    /// at the same position (same NPC is quest giver + turn-in), the
    /// highest-priority marker type wins.
    /// </summary>
    private static List<MarkerEntry> DeduplicateByPosition(IReadOnlyList<MarkerEntry> markers)
    {
        var best = new Dictionary<long, int>(); // posKey → index in result
        var result = new List<MarkerEntry>(markers.Count);

        for (int i = 0; i < markers.Count; i++)
        {
            var entry = markers[i];
            long key = PositionKey(entry.X, entry.Y, entry.Z);

            if (best.TryGetValue(key, out int existingIdx))
            {
                // Lower enum value = higher priority
                if (entry.Type < result[existingIdx].Type)
                    result[existingIdx] = entry;
            }
            else
            {
                best[key] = result.Count;
                result.Add(entry);
            }
        }

        return result;
    }

    private static long PositionKey(float x, float y, float z)
    {
        int ix = (int)(x * 10f);
        int iy = (int)(y * 10f);
        int iz = (int)(z * 10f);
        return ((long)ix << 40) | ((long)(iy & 0xFFFFF) << 20) | (long)(iz & 0xFFFFF);
    }
}

using TMPro;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Types of world markers. Priority order (highest first) determines
/// which icon shows when multiple quests target the same NPC.
/// </summary>
public enum MarkerType
{
    TurnInReady,         // circle-question gold — can turn in now
    TurnInRepeatReady,   // circle-question blue — repeatable, can turn in
    Objective,           // circle-dot orange — step objective or drop source
    QuestGiver,          // star gold — new quest available
    QuestGiverRepeat,    // star blue — repeatable quest available
    TurnInPending,       // circle-question grey — quest active, missing items
    DeadSpawn,           // clock red — respawn timer
    NightSpawn,          // moon pale-blue — night-only, currently daytime
    ZoneReentry,         // clock grey — directly placed, re-enter zone to respawn
}

/// <summary>
/// Manages a pool of reusable billboard marker GameObjects. Each marker
/// uses two TextMeshPro (world-space 3D) components: a Font Awesome icon
/// glyph and a Roboto sub-text label. SDF rendering provides anti-aliased
/// edges with a dark outline for contrast, and depth occlusion via the
/// standard Distance Field shader.
/// </summary>
public sealed class MarkerPool
{
    private const int InitialCapacity = 32;

    private readonly GameObject _root;
    private readonly List<MarkerInstance> _pool;
    private int _activeCount;

    /// <summary>Number of currently active markers.</summary>
    public int ActiveCount => _activeCount;

    public MarkerPool()
    {
        _root = new GameObject("AdventureGuide_WorldMarkers");
        UnityEngine.Object.DontDestroyOnLoad(_root);
        _root.hideFlags = HideFlags.HideAndDontSave;

        _pool = new List<MarkerInstance>(InitialCapacity);
        _activeCount = 0;

        for (int i = 0; i < InitialCapacity; i++)
            CreateInstance();
    }

    /// <summary>
    /// Get or create a marker instance at the given index.
    /// </summary>
    public MarkerInstance Get(int index)
    {
        while (index >= _pool.Count)
            CreateInstance();
        return _pool[index];
    }

    /// <summary>Set the number of active markers. Deactivates extras.</summary>
    public void SetActiveCount(int count)
    {
        for (int i = count; i < _activeCount; i++)
            _pool[i].SetActive(false);
        _activeCount = count;
    }

    /// <summary>Deactivate all markers.</summary>
    public void DeactivateAll()
    {
        for (int i = 0; i < _activeCount; i++)
            _pool[i].SetActive(false);
        _activeCount = 0;
    }


    /// <summary>Destroy all pooled objects.</summary>
    public void Destroy()
    {
        UnityEngine.Object.Destroy(_root);
        _pool.Clear();
        _activeCount = 0;
    }

    private void CreateInstance()
    {

        var obj = new GameObject($"Marker_{_pool.Count}");
        obj.transform.SetParent(_root.transform);
        // Billboard via game's NamePlate component on the root so both
        // children rotate together. Root uses POSITIVE scale (LookAt breaks
        // with negative scale). Each TMP child gets localScale (-1,1,1)
        // to correct the text mirroring that LookAt introduces.
        obj.transform.localScale = Vector3.one;
        obj.AddComponent<NamePlate>();
        // Icon: Font Awesome glyph via TextMeshPro SDF
        var iconObj = new GameObject("Icon");
        iconObj.transform.SetParent(obj.transform);
        iconObj.transform.localPosition = Vector3.zero;
        var icon = iconObj.AddComponent<TextMeshPro>();
        icon.alignment = TextAlignmentOptions.Center;
        icon.enableWordWrapping = false;
        icon.overflowMode = TextOverflowModes.Overflow;
        icon.richText = false;
        // Font assigned during Configure, not here — fonts may not be
        // ready yet when the pool pre-creates markers.
        iconObj.transform.localScale = new Vector3(-1f, 1f, 1f);

        // Sub-text: Roboto label below icon
        var subObj = new GameObject("SubText");
        subObj.transform.SetParent(obj.transform);
        var sub = subObj.AddComponent<TextMeshPro>();
        sub.alignment = TextAlignmentOptions.Top;
        sub.enableWordWrapping = true;
        sub.overflowMode = TextOverflowModes.Truncate;
        sub.richText = false;
        sub.color = MarkerInstance.SubTextColor;
        // Font assigned during Configure.
        subObj.transform.localScale = new Vector3(-1f, 1f, 1f);

        // Both TMP components use RectTransform — set reasonable size
        var iconRect = icon.rectTransform;
        iconRect.sizeDelta = new Vector2(4f, 4f);
        var subRect = sub.rectTransform;
        subRect.sizeDelta = new Vector2(8f, 3f);

        obj.SetActive(false);

        _pool.Add(new MarkerInstance(obj, icon, sub));
    }
}

/// <summary>
/// A single marker instance with TextMeshPro icon and sub-text.
/// </summary>
public sealed class MarkerInstance
{
    // ── Icon sizes per marker type ──────────────────────────────
    private const float SizeTier1 = 8f;    // TurnInReady, TurnInRepeatReady
    private const float SizeTier2 = 7f;    // QuestGiver, QuestGiverRepeat, Objective
    private const float SizeObjective = 6.5f;
    private const float SizeTier3 = 6f;    // TurnInPending
    private const float SizeInfo = 5.5f;   // DeadSpawn, NightSpawn

    // ── Face colors ─────────────────────────────────────────────
    private static readonly Color Gold = new(1.0f, 0.85f, 0.3f, 1f);
    private static readonly Color Blue = new(0.4f, 0.65f, 1.0f, 1f);
    private static readonly Color Orange = new(1.0f, 0.6f, 0.25f, 1f);
    private static readonly Color Grey = new(0.5f, 0.5f, 0.5f, 1f);
    private static readonly Color MutedRed = new(0.65f, 0.35f, 0.35f, 1f);
    private static readonly Color PaleBlue = new(0.55f, 0.6f, 0.8f, 1f);

    // ── Sub-text defaults ──────────────────────────────────────────────────
    internal static readonly Color SubTextColor = new(0.92f, 0.92f, 0.92f, 1f);

    // ── Distance fade ───────────────────────────────────────────
    // Icon fades 100-150m. Sub-text fades earlier: 60-80m.
    private const float IconFadeStart = 100f;
    private const float IconFadeEnd = 150f;
    private const float SubFadeStart = 60f;
    private const float SubFadeEnd = 80f;

    // ── Glyph + color lookup ────────────────────────────────────
    private static readonly (char glyph, Color color, float size)[] TypeVisuals =
    {
        (MarkerFonts.CircleQuestion,  Gold,     SizeTier1),      // TurnInReady
        (MarkerFonts.CircleQuestion,  Blue,     SizeTier1),      // TurnInRepeatReady
        (MarkerFonts.CircleDot,       Orange,   SizeObjective),  // Objective
        (MarkerFonts.Star,            Gold,     SizeTier2),      // QuestGiver
        (MarkerFonts.Star,            Blue,     SizeTier2),      // QuestGiverRepeat
        (MarkerFonts.CircleQuestion,  Grey,     SizeTier3),      // TurnInPending
        (MarkerFonts.Clock,           MutedRed, SizeInfo),       // DeadSpawn
        (MarkerFonts.Moon,            PaleBlue, SizeInfo),       // NightSpawn
        (MarkerFonts.Clock,           Grey,     SizeInfo),       // ZoneReentry
    };

    public readonly GameObject Root;
    private readonly TextMeshPro _icon;
    private readonly TextMeshPro _subText;

    private Color _baseIconColor;

    public MarkerInstance(GameObject root, TextMeshPro icon, TextMeshPro subText)
    {
        Root = root;
        _icon = icon;
        _subText = subText;
    }

    /// <summary>Configure the marker's visual appearance for a given type.</summary>
    public void Configure(MarkerType type, string? subText,
        float markerScale, float iconSize, float subTextSize,
        float iconYOffset, float subTextYOffset)
    {
        int idx = (int)type;
        var (glyph, color, _) = TypeVisuals[idx];

        Root.transform.localScale = Vector3.one * markerScale;

        // Assign fonts every Configure — fonts load lazily and may not
        // have been ready when the marker was first created.
        if (MarkerFonts.IconFont != null)
            _icon.font = MarkerFonts.IconFont;
        if (MarkerFonts.SubTextFont != null)
            _subText.font = MarkerFonts.SubTextFont;

        _icon.text = glyph.ToString();
        _icon.fontSize = iconSize;
        _icon.color = color;
        _baseIconColor = color;
        _icon.transform.localPosition = new Vector3(0f, iconYOffset, 0f);

        _subText.fontSize = subTextSize;
        _subText.transform.localPosition = new Vector3(0f, subTextYOffset, 0f);

        if (!string.IsNullOrEmpty(subText))
        {
            _subText.text = subText;
            _subText.gameObject.SetActive(true);
        }
        else
        {
            _subText.text = "";
            _subText.gameObject.SetActive(false);
        }
    }

    /// <summary>Update only the sub-text without re-configuring the full marker.</summary>
    public void UpdateSubText(string? subText)
    {
        if (!string.IsNullOrEmpty(subText))
        {
            _subText.text = subText;
            _subText.gameObject.SetActive(true);
        }
        else
        {
            _subText.text = "";
            _subText.gameObject.SetActive(false);
        }
    }

    /// <summary>Set the world position of the marker.</summary>
    public void SetPosition(Vector3 position)
    {
        Root.transform.position = position;
    }

    /// <summary>
    /// Apply distance-based fade. Icon fades 80-100m, sub-text fades
    /// 40-60m. Beyond fade end, both are invisible.
    /// </summary>
    public void SetAlpha(float distance)
    {
        float iconAlpha = ComputeFade(distance, IconFadeStart, IconFadeEnd);
        float subAlpha = ComputeFade(distance, SubFadeStart, SubFadeEnd);

        var c = _baseIconColor;
        c.a = iconAlpha;
        _icon.color = c;

        if (_subText.gameObject.activeSelf)
        {
            var sc = SubTextColor;
            sc.a = subAlpha;
            _subText.color = sc;
        }
    }

    public void SetActive(bool active) => Root.SetActive(active);

    private static float ComputeFade(float distance, float fadeStart, float fadeEnd)
    {
        if (distance > fadeEnd) return 0f;
        if (distance > fadeStart)
            return 1f - (distance - fadeStart) / (fadeEnd - fadeStart);
        return 1f;
    }
}

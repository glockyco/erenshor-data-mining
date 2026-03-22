using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Types of world markers. Priority order (highest first) determines
/// which icon shows when multiple quests target the same NPC.
/// </summary>
public enum MarkerType
{
    TurnInReady,         // ? gold — can turn in now
    TurnInRepeatReady,   // ? blue — repeatable, can turn in
    Objective,           // target — step objective or drop source
    QuestGiver,          // ! gold — new quest available
    QuestGiverRepeat,    // ! blue — repeatable quest available
    TurnInPending,       // ? grey — quest active, missing items
    DeadSpawn,           // skull — respawn timer
    NightSpawn,          // moon — night-only, currently daytime
}

/// <summary>
/// Manages a pool of reusable billboard marker GameObjects. Each marker
/// has a background circle sprite and a foreground text glyph (TextMesh).
/// Markers are activated/deactivated, never destroyed mid-session.
///
/// The pool lives under a hidden DontDestroyOnLoad parent and is
/// destroyed on plugin cleanup.
/// </summary>
public sealed class MarkerPool
{
    private const float MarkerScale = 0.5f;
    private const int InitialCapacity = 32;

    private readonly GameObject _root;
    private readonly Sprite _circleSprite;
    private readonly MarkerInstance[] _pool;
    private int _count;
    private int _activeCount;

    /// <summary>Number of currently active markers.</summary>
    public int ActiveCount => _activeCount;

    public MarkerPool()
    {
        _root = new GameObject("AdventureGuide_WorldMarkers");
        UnityEngine.Object.DontDestroyOnLoad(_root);
        _root.hideFlags = HideFlags.HideAndDontSave;

        _circleSprite = CreateCircleSprite();
        _pool = new MarkerInstance[InitialCapacity * 2]; // room to grow
        _count = 0;
        _activeCount = 0;

        // Pre-allocate initial pool
        for (int i = 0; i < InitialCapacity; i++)
            CreateInstance();
    }

    /// <summary>
    /// Get or create a marker instance at the given index.
    /// Call SetMarker to configure it, then Activate.
    /// </summary>
    public MarkerInstance Get(int index)
    {
        while (index >= _count)
            CreateInstance();
        return _pool[index];
    }

    /// <summary>Set the number of active markers. Deactivates extras.</summary>
    public void SetActiveCount(int count)
    {
        // Deactivate markers beyond the new count
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

    /// <summary>Update billboard rotation for all active markers.</summary>
    public void UpdateBillboards(Quaternion cameraRotation)
    {
        for (int i = 0; i < _activeCount; i++)
            _pool[i].Root.transform.rotation = cameraRotation;
    }

    /// <summary>Destroy all pooled objects.</summary>
    public void Destroy()
    {
        UnityEngine.Object.Destroy(_root);
        _count = 0;
        _activeCount = 0;
    }

    private void CreateInstance()
    {
        if (_count >= _pool.Length)
        {
            // Pool exhausted — this shouldn't happen with reasonable marker counts
            Plugin.Log.LogWarning($"MarkerPool capacity {_pool.Length} exhausted");
            return;
        }

        var obj = new GameObject($"Marker_{_count}");
        obj.transform.SetParent(_root.transform);
        obj.transform.localScale = Vector3.one * MarkerScale;

        // Background circle
        var bgObj = new GameObject("BG");
        bgObj.transform.SetParent(obj.transform);
        bgObj.transform.localPosition = Vector3.zero;
        bgObj.transform.localScale = Vector3.one;
        var bg = bgObj.AddComponent<SpriteRenderer>();
        bg.sprite = _circleSprite;
        bg.sortingOrder = 100;

        // Foreground glyph text
        var textObj = new GameObject("Text");
        textObj.transform.SetParent(obj.transform);
        textObj.transform.localPosition = new Vector3(0f, 0.05f, -0.01f);
        var text = textObj.AddComponent<TextMesh>();
        text.alignment = TextAlignment.Center;
        text.anchor = TextAnchor.MiddleCenter;
        text.characterSize = 0.5f;
        text.fontSize = 48;
        text.fontStyle = FontStyle.Bold;
        text.richText = false;

        // Sub-text for keywords, item names, progress
        var subObj = new GameObject("SubText");
        subObj.transform.SetParent(obj.transform);
        subObj.transform.localPosition = new Vector3(0f, -0.7f, -0.01f);
        var sub = subObj.AddComponent<TextMesh>();
        sub.alignment = TextAlignment.Center;
        sub.anchor = TextAnchor.UpperCenter;
        sub.characterSize = 0.2f;
        sub.fontSize = 36;
        sub.fontStyle = FontStyle.Normal;
        sub.richText = false;
        sub.color = Color.white;

        obj.SetActive(false);

        _pool[_count] = new MarkerInstance(obj, bg, text, sub);
        _count++;
    }

    /// <summary>
    /// Create a 64x64 filled circle texture with soft anti-aliased edges.
    /// Used as the background behind glyph text.
    /// </summary>
    private static Sprite CreateCircleSprite()
    {
        const int size = 64;
        const float radius = size / 2f;
        const float edgeSoftness = 2f;

        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
        tex.filterMode = FilterMode.Bilinear;
        tex.wrapMode = TextureWrapMode.Clamp;

        var pixels = new Color[size * size];
        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float dx = x - radius + 0.5f;
                float dy = y - radius + 0.5f;
                float dist = Mathf.Sqrt(dx * dx + dy * dy);

                // Smooth edge: full inside, fade at border, transparent outside
                float alpha = Mathf.Clamp01((radius - dist) / edgeSoftness);
                pixels[y * size + x] = new Color(1f, 1f, 1f, alpha);
            }
        }

        tex.SetPixels(pixels);
        tex.Apply(false, true);

        return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 64f);
    }
}

/// <summary>
/// A single marker instance in the pool. Holds references to the
/// root GameObject, background sprite, glyph text, and sub-text.
/// </summary>
public sealed class MarkerInstance
{
    // Colors for marker types
    private static readonly Color GoldBg = new(0.85f, 0.65f, 0.10f, 0.90f);
    private static readonly Color BlueBg = new(0.20f, 0.50f, 0.85f, 0.90f);
    private static readonly Color GreyBg = new(0.45f, 0.45f, 0.45f, 0.80f);
    private static readonly Color DimBg = new(0.30f, 0.30f, 0.30f, 0.70f);
    private static readonly Color DarkText = new(0.10f, 0.08f, 0.05f, 1.0f);
    private static readonly Color LightText = new(1.0f, 0.95f, 0.85f, 1.0f);

    public readonly GameObject Root;
    private readonly SpriteRenderer _bg;
    private readonly TextMesh _glyph;
    private readonly TextMesh _subText;

    public MarkerInstance(GameObject root, SpriteRenderer bg, TextMesh glyph, TextMesh subText)
    {
        Root = root;
        _bg = bg;
        _glyph = glyph;
        _subText = subText;
    }

    /// <summary>Configure the marker's visual appearance.</summary>
    public void Configure(MarkerType type, string? subText)
    {
        switch (type)
        {
            case MarkerType.QuestGiver:
                _bg.color = GoldBg;
                _glyph.text = "!";
                _glyph.color = DarkText;
                break;
            case MarkerType.QuestGiverRepeat:
                _bg.color = BlueBg;
                _glyph.text = "!";
                _glyph.color = LightText;
                break;
            case MarkerType.TurnInReady:
                _bg.color = GoldBg;
                _glyph.text = "?";
                _glyph.color = DarkText;
                break;
            case MarkerType.TurnInRepeatReady:
                _bg.color = BlueBg;
                _glyph.text = "?";
                _glyph.color = LightText;
                break;
            case MarkerType.TurnInPending:
                _bg.color = GreyBg;
                _glyph.text = "?";
                _glyph.color = LightText;
                break;
            case MarkerType.Objective:
                _bg.color = GoldBg;
                _glyph.text = "\u25C6"; // filled diamond ◆
                _glyph.color = DarkText;
                break;
            case MarkerType.DeadSpawn:
                _bg.color = DimBg;
                _glyph.text = "\u2620"; // skull ☠ — may not render, fallback to X
                _glyph.color = LightText;
                break;
            case MarkerType.NightSpawn:
                _bg.color = DimBg;
                _glyph.text = "\u263D"; // crescent moon ☽ — may not render, fallback to *
                _glyph.color = LightText;
                break;
        }

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

    /// <summary>Set the alpha for distance fade.</summary>
    public void SetAlpha(float alpha)
    {
        var bgColor = _bg.color;
        bgColor.a = Mathf.Min(bgColor.a, alpha);
        _bg.color = bgColor;

        var glyphColor = _glyph.color;
        glyphColor.a = alpha;
        _glyph.color = glyphColor;

        var subColor = _subText.color;
        subColor.a = alpha;
        _subText.color = subColor;
    }

    public void SetActive(bool active) => Root.SetActive(active);
}

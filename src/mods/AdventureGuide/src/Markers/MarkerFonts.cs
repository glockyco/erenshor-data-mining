using TMPro;
using UnityEngine;

namespace AdventureGuide.Markers;

/// <summary>
/// Lazily creates and caches TMP_FontAsset objects for world markers.
/// Two font assets: one for Font Awesome icon glyphs, one for Roboto
/// sub-text labels. Both use the depth-occluded Distance Field shader
/// with a dark outline for contrast against any world background.
/// </summary>
internal static class MarkerFonts
{
    // Font Awesome 7 Free-Regular glyph codepoints. The Free-Regular
    // weight only has outlined icons — solid-weight glyphs (circle-exclamation,
    // crosshairs, skull) are not available. Validated at init time.
    internal const char CircleQuestion = '\uf059';  // turn-in markers
    internal const char Star = '\uf005';             // quest giver markers
    internal const char CircleDot = '\uf192';        // objective markers
    internal const char Clock = '\uf017';             // dead spawn timer
    internal const char Moon = '\uf186';              // night spawn

    private static readonly char[] RequiredGlyphs =
    {
        CircleQuestion, Star, CircleDot, Clock, Moon,
    };

    // Outline settings — dark border for contrast on any background
    private static readonly Color OutlineColor = new(0.04f, 0.03f, 0.02f, 0.85f);
    private const float OutlineWidth = 0.18f;

    private static TMP_FontAsset? _iconFont;
    private static TMP_FontAsset? _subTextFont;
    private static bool _initialized;

    /// <summary>Font asset for Font Awesome icon glyphs. Null until ready.</summary>
    public static TMP_FontAsset? IconFont
    {
        get
        {
            EnsureInitialized();
            return _iconFont;
        }
    }

    /// <summary>Font asset for Roboto sub-text labels. Null until ready.</summary>
    public static TMP_FontAsset? SubTextFont
    {
        get
        {
            EnsureInitialized();
            return _subTextFont;
        }
    }

    /// <summary>True when both fonts are loaded and ready to use.</summary>
    public static bool IsReady
    {
        get
        {
            EnsureInitialized();
            return _initialized;
        }
    }

    /// <summary>
    /// Release cached font assets. Call from Plugin.OnDestroy.
    /// </summary>
    public static void Destroy()
    {
        if (_iconFont != null) UnityEngine.Object.Destroy(_iconFont);
        if (_subTextFont != null) UnityEngine.Object.Destroy(_subTextFont);
        _iconFont = null;
        _subTextFont = null;
        _initialized = false;
    }

    private static void EnsureInitialized()
    {
        if (_initialized) return;

        var sdfShader = Shader.Find("TextMeshPro/Distance Field");
        if (sdfShader == null)
        {
            // Shader not loaded yet — retry next access
            return;
        }

        _iconFont = CreateIconFont(sdfShader);
        _subTextFont = CreateSubTextFont(sdfShader);

        if (_iconFont == null || _subTextFont == null)
        {
            // Font sources not available yet (GameData not ready) —
            // clean up any partial result and retry next access.
            if (_iconFont != null) UnityEngine.Object.Destroy(_iconFont);
            if (_subTextFont != null) UnityEngine.Object.Destroy(_subTextFont);
            _iconFont = null;
            _subTextFont = null;
            return;
        }

        _initialized = true;
    }

    private static TMP_FontAsset? CreateIconFont(Shader sdfShader)
    {
        var faFont = GameData.Misc?.FontAwesome;
        if (faFont == null)
            return null;

        var asset = TMP_FontAsset.CreateFontAsset(faFont);
        if (asset == null)
        {
            Plugin.Log.LogError("MarkerFonts: Failed to create TMP_FontAsset from Font Awesome");
            return null;
        }

        asset.name = "MarkerIcons-FA";
        ConfigureMaterial(asset.material, sdfShader);

        // Pre-populate the dynamic atlas with required glyphs. Without
        // this, HasCharacter returns false for un-rendered characters.
        var glyphString = new string(RequiredGlyphs);
        if (!asset.TryAddCharacters(glyphString, out string missing, true))
        {
            UnityEngine.Object.Destroy(asset);
            return null;
        }

        // Verify glyphs are actually present in the atlas. TryAddCharacters
        // can return true before the font data is fully loaded during early
        // scene initialization. If any glyph is missing, retry next frame.
        foreach (var ch in RequiredGlyphs)
        {
            if (!asset.HasCharacter(ch, searchFallbacks: false))
            {
                UnityEngine.Object.Destroy(asset);
                return null;
            }
        }

        Plugin.Log.LogInfo("MarkerFonts: Icon font created (Font Awesome SDF)");
        return asset;
    }

    private static TMP_FontAsset? CreateSubTextFont(Shader sdfShader)
    {
        Font? roboto = FindFont("Roboto-Regular");
        if (roboto == null)
            return null;

        var asset = TMP_FontAsset.CreateFontAsset(roboto);
        if (asset == null)
        {
            Plugin.Log.LogError("MarkerFonts: Failed to create TMP_FontAsset from Roboto");
            return null;
        }

        asset.name = "MarkerSubText-Roboto";
        ConfigureMaterial(asset.material, sdfShader);

        Plugin.Log.LogInfo("MarkerFonts: Sub-text font created (Roboto SDF)");
        return asset;
    }

    private static void ConfigureMaterial(Material material, Shader sdfShader)
    {
        // Swap from Mobile/Distance Field to full Distance Field for
        // outline support and proper depth testing.
        material.shader = sdfShader;

        material.SetColor("_OutlineColor", OutlineColor);
        material.SetFloat("_OutlineWidth", OutlineWidth);
        material.EnableKeyword("OUTLINE_ON");
    }

    private static Font? FindFont(string name)
    {
        var fonts = Resources.FindObjectsOfTypeAll(typeof(Font));
        foreach (var f in fonts)
        {
            if (((Font)f).name == name)
                return (Font)f;
        }
        return null;
    }
}

using TMPro;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Lazily creates and caches TMP_FontAsset objects for world markers.
/// Two font assets: one for Font Awesome icon glyphs, one for Roboto
/// sub-text labels. Both use the depth-occluded Distance Field shader
/// with a dark outline for contrast against any world background.
/// </summary>
internal static class MarkerFonts
{
    // Font Awesome codepoints used by markers. Validated at init time.
    internal const char CircleQuestion = '\uf059';
    internal const char CircleExclamation = '\uf06a';
    internal const char Crosshairs = '\uf05b';
    internal const char Skull = '\uf54c';
    internal const char Moon = '\uf186';

    private static readonly char[] RequiredGlyphs =
    {
        CircleQuestion, CircleExclamation, Crosshairs, Skull, Moon,
    };

    // Outline settings — dark border for contrast on any background
    private static readonly Color OutlineColor = new(0.04f, 0.03f, 0.02f, 0.85f);
    private const float OutlineWidth = 0.18f;

    private static TMP_FontAsset? _iconFont;
    private static TMP_FontAsset? _subTextFont;
    private static bool _initialized;
    private static bool _initFailed;

    /// <summary>Font asset for Font Awesome icon glyphs. Null if init failed.</summary>
    public static TMP_FontAsset? IconFont
    {
        get
        {
            EnsureInitialized();
            return _iconFont;
        }
    }

    /// <summary>Font asset for Roboto sub-text labels. Null if init failed.</summary>
    public static TMP_FontAsset? SubTextFont
    {
        get
        {
            EnsureInitialized();
            return _subTextFont;
        }
    }

    /// <summary>True if initialization was attempted and failed.</summary>
    public static bool Failed => _initFailed;

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
        _initFailed = false;
    }

    private static void EnsureInitialized()
    {
        if (_initialized) return;
        _initialized = true;

        var sdfShader = Shader.Find("TextMeshPro/Distance Field");
        if (sdfShader == null)
        {
            Plugin.Log.LogError("MarkerFonts: TextMeshPro/Distance Field shader not found");
            _initFailed = true;
            return;
        }

        _iconFont = CreateIconFont(sdfShader);
        _subTextFont = CreateSubTextFont(sdfShader);

        if (_iconFont == null || _subTextFont == null)
            _initFailed = true;
    }

    private static TMP_FontAsset? CreateIconFont(Shader sdfShader)
    {
        var faFont = GameData.Misc?.FontAwesome;
        if (faFont == null)
        {
            Plugin.Log.LogError("MarkerFonts: GameData.Misc.FontAwesome is null");
            return null;
        }

        var asset = TMP_FontAsset.CreateFontAsset(faFont);
        if (asset == null)
        {
            Plugin.Log.LogError("MarkerFonts: Failed to create TMP_FontAsset from Font Awesome");
            return null;
        }

        asset.name = "MarkerIcons-FA";
        ConfigureMaterial(asset.material, sdfShader);

        // Validate all required glyphs
        foreach (char glyph in RequiredGlyphs)
        {
            if (!asset.HasCharacter(glyph))
            {
                Plugin.Log.LogError(
                    $"MarkerFonts: Font Awesome missing glyph U+{(int)glyph:X4}");
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
        {
            Plugin.Log.LogError("MarkerFonts: Roboto-Regular font not found in game");
            return null;
        }

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

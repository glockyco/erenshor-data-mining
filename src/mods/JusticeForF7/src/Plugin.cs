using BepInEx;
using HarmonyLib;
using JusticeForF7.Patches;
using UnityEngine.SceneManagement;

namespace JusticeForF7;

/// <summary>
/// Main plugin entry point for Justice for F7.
/// Fixes the F7 "Hide UI" key to also hide world-space UI elements
/// (nameplates, damage numbers, target rings, XP orbs, loot prompts).
/// </summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    private Harmony? _harmony;
    private WorldUIHider? _hider;

    private void Awake()
    {
        var enabled = Config.Bind(
            "General",
            "Enabled",
            true,
            "Master switch. When false, F7 behaves as vanilla.");

        if (!enabled.Value)
        {
            Logger.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded (disabled via config)");
            return;
        }

        var enableLogging = Config.Bind(
            "General",
            "EnableLogging",
            true,
            "Enable debug logging. Set to false to silence all mod log output.");

        var rescanInterval = Config.Bind(
            "General",
            "RescanInterval",
            30,
            "Frames between re-scans while UI is hidden (0 = disable re-scan).");

        var hideNameplates = Config.Bind(
            "Elements",
            "HideNameplates",
            true,
            "Hide NPC, SimPlayer, and player nameplates.");

        var hideDamageNumbers = Config.Bind(
            "Elements",
            "HideDamageNumbers",
            true,
            "Hide floating damage and heal numbers.");

        var hideTargetRings = Config.Bind(
            "Elements",
            "HideTargetRings",
            true,
            "Hide the selection ring under targeted characters.");

        var hideXPOrbs = Config.Bind(
            "Elements",
            "HideXPOrbs",
            true,
            "Hide XP orb particles.");

        var hideCastBars = Config.Bind(
            "Elements",
            "HideCastBars",
            true,
            "Hide NPC and SimPlayer cast bars above nameplates.");

        var hideOtherWorldText = Config.Bind(
            "Elements",
            "HideOtherWorldText",
            true,
            "Hide remaining world-space text (loot prompts, etc.).");

        _hider = new WorldUIHider(
            Logger,
            enableLogging,
            hideNameplates,
            hideDamageNumbers,
            hideTargetRings,
            hideXPOrbs,
            hideCastBars,
            hideOtherWorldText,
            rescanInterval);

        // Inject hider into static patch properties before patching
        TypeTextPatch.Hider = _hider;
        DmgPopPatch.Hider = _hider;
        XPBubPatch.Hider = _hider;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        SceneManager.sceneLoaded += OnSceneLoaded;

        if (enableLogging.Value)
            Logger.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        _hider?.OnSceneLoaded();
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        _harmony?.UnpatchSelf();
    }
}

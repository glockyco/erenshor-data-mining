using HarmonyLib;
using JusticeForF7.Patches;
using Lunaris;
using UnityEngine.SceneManagement;

namespace JusticeForF7;

/// <summary>
/// Native Lunaris entry point for Justice for F7. Extends the F7 "Hide UI" key
/// to also hide world-space UI elements (nameplates, damage numbers, target
/// rings, XP orbs, cast bars, loot prompts).
/// </summary>
[LunarisPlugin(
    "Justice for F7",
    PluginInfo.Version,
    "WoW_Much",
    "Extend the F7 Hide UI key to hide world-space UI too."
)]
[LunarisPermission(LunarisPermission.Harmony | LunarisPermission.LunarisPlugin)]
public sealed class Plugin : LunarisPlugin
{
    private Harmony? _harmony;
    private WorldUIHider? _hider;

    private void Awake()
    {
        var settings = Config.Register<JusticeSettings>().Get();

        if (!settings.Enabled)
        {
            Logging.LogInfo(
                $"{PluginInfo.Name} v{PluginInfo.Version} loaded (disabled via config)"
            );
            return;
        }

        _hider = new WorldUIHider(Logging, settings);

        // Inject hider into static patch properties before patching
        TypeTextPatch.Hider = _hider;
        DmgPopPatch.Hider = _hider;
        XPBubPatch.Hider = _hider;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        SceneManager.sceneLoaded += OnSceneLoaded;

        if (settings.EnableLogging)
            Logging.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        // Reset patch state to re-sync with new scene's canvas state
        TypeTextPatch.ResetState();
        _hider?.OnSceneLoaded();
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        _harmony?.UnpatchSelf();

        // Restore any world UI we hid so unloading mid-hide does not leave
        // renderers disabled with no mod left to re-enable them.
        _hider?.OnUIShown();

        TypeTextPatch.Hider = null;
        DmgPopPatch.Hider = null;
        XPBubPatch.Hider = null;
        TypeTextPatch.ResetState();
    }
}

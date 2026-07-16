using HarmonyLib;
using JusticeForF7.Patches;
using UnityEngine.SceneManagement;

namespace JusticeForF7;

/// <summary>
/// Loader-neutral lifecycle owner for Justice. Adapters only supply settings and
/// logging, while this class owns patching, scene subscriptions, and cleanup.
/// </summary>
internal sealed class JusticeRuntime
{
    private readonly IModLogger _log;
    private readonly IJusticeSettings _settings;

    private Harmony? _harmony;
    private WorldUIHider? _hider;
    private bool _running;
    private bool _disabledReported;

    public JusticeRuntime(IModLogger log, IJusticeSettings settings)
    {
        _log = log;
        _settings = settings;
    }

    /// <summary>Starts the mod at most once for the current adapter lifetime.</summary>
    public void Start()
    {
        if (_running)
            return;

        if (!_settings.Enabled)
        {
            ReportDisabled();
            return;
        }

        _disabledReported = false;

        _hider = new WorldUIHider(_log, _settings);
        TypeTextPatch.Hider = _hider;
        DmgPopPatch.Hider = _hider;
        XPBubPatch.Hider = _hider;

        _harmony = new Harmony(PluginInfo.GUID);
        try
        {
            _harmony.PatchAll();
            SceneManager.sceneLoaded += OnSceneLoaded;
            _running = true;
        }
        catch
        {
            Stop();
            throw;
        }

        if (_settings.EnableLogging)
            _log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    /// <summary>Applies live changes to the master enable setting.</summary>
    public void Tick()
    {
        if (_settings.Enabled)
        {
            Start();
        }
        else if (_running)
        {
            Stop();
            ReportDisabled();
        }
        else
        {
            ReportDisabled();
        }
    }

    /// <summary>Stops the mod and restores every piece of game state it owns.</summary>
    public void Stop()
    {
        if (_running)
            SceneManager.sceneLoaded -= OnSceneLoaded;

        _harmony?.UnpatchSelf();
        _harmony = null;

        _hider?.OnUIShown();
        _hider = null;

        TypeTextPatch.Hider = null;
        DmgPopPatch.Hider = null;
        XPBubPatch.Hider = null;
        TypeTextPatch.ResetState();

        _running = false;
    }

    private void ReportDisabled()
    {
        if (_disabledReported)
            return;

        _disabledReported = true;
        _log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded (disabled via config)");
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        TypeTextPatch.ResetState();
        _hider?.OnSceneLoaded();
    }
}

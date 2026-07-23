using HarmonyLib;
using JusticeForF7.Patches;
using UnityEngine.SceneManagement;

namespace JusticeForF7;

/// <summary>
/// Loader-neutral lifecycle owner for Justice. Adapters only supply settings and
/// logging, while this class owns patching, scene subscriptions, and cleanup.
/// </summary>
internal sealed class JusticeRuntime : IJusticeLifecycleEffects
{
    private readonly IModLogger _log;
    private readonly IJusticeSettings _settings;
    private readonly CanvasVisibilityObserver _canvasVisibility = new();
    private readonly JusticeLifecycle _lifecycle;

    private Harmony? _harmony;
    private WorldUIHider? _hider;

    public JusticeRuntime(IModLogger log, IJusticeSettings settings)
    {
        _log = log;
        _settings = settings;
        _lifecycle = new JusticeLifecycle(this);
    }

    /// <summary>Starts the mod at most once for the current adapter lifetime.</summary>
    public void Start() => _lifecycle.Start(_settings.Enabled);

    /// <summary>Applies live changes to the master enable setting.</summary>
    public void Tick() => _lifecycle.Tick(_settings.Enabled);

    /// <summary>Stops the mod and restores every piece of game state it owns.</summary>
    public void Stop() => _lifecycle.Stop();

    void IJusticeLifecycleEffects.Start()
    {
        try
        {
            _hider = new WorldUIHider(_log, _settings);
            NamePlatePatch.Hider = _hider;
            NpcNamePlatePatch.Hider = _hider;
            DmgPopPatch.Hider = _hider;
            XPBubPatch.Hider = _hider;

            _harmony = new Harmony(PluginInfo.GUID);
            _harmony.PatchAll();
            SceneManager.sceneLoaded += OnSceneLoaded;

            if (_settings.EnableLogging)
                _log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
        }
        catch
        {
            // Startup must leave no patches, subscriptions, or injected static
            // references behind so a later retry can start from a clean state.
            ((IJusticeLifecycleEffects)this).Stop();
            throw;
        }
    }

    void IJusticeLifecycleEffects.Stop()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;

        try
        {
            _harmony?.UnpatchSelf();
        }
        finally
        {
            _harmony = null;
            try
            {
                _hider?.OnUIShown();
            }
            finally
            {
                _hider = null;
                _canvasVisibility.Reset();
                NamePlatePatch.Hider = null;
                NpcNamePlatePatch.Hider = null;
                DmgPopPatch.Hider = null;
                XPBubPatch.Hider = null;
            }
        }
    }

    void IJusticeLifecycleEffects.Tick()
    {
        if (_hider != null)
            _canvasVisibility.Tick(_hider);
    }

    void IJusticeLifecycleEffects.SceneLoaded()
    {
        _canvasVisibility.Reset();
        _hider?.OnSceneLoaded();
    }

    void IJusticeLifecycleEffects.ReportDisabled()
    {
        _log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded (disabled via config)");
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        _lifecycle.SceneLoaded();
    }
}

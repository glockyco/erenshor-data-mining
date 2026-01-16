using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using Microsoft.Extensions.DependencyInjection;

namespace InteractiveMapCompanion;

/// <summary>
/// Main plugin entry point for Interactive Map Companion.
/// Broadcasts real-time game state to the interactive map website via WebSocket.
/// </summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    internal static ManualLogSource Log { get; private set; } = null!;

    private ServiceProvider? _services;
    private Harmony? _harmony;

    private void Awake()
    {
        Log = Logger;

        _services = ConfigureServices();
        _harmony = new Harmony(PluginInfo.GUID);

        // TODO: Configure patches when implemented
        // _harmony.PatchAll();

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private ServiceProvider ConfigureServices()
    {
        var services = new ServiceCollection();

        // TODO: Register services as they are implemented
        // services.AddSingleton<IEntityTracker, EntityTrackerAdapter>();
        // services.AddSingleton<IWebSocketServer, WebSocketServer>();
        // services.AddSingleton<IStateManager, StateManager>();

        return services.BuildServiceProvider();
    }

    private void OnDestroy()
    {
        _harmony?.UnpatchSelf();
        _services?.Dispose();
    }
}

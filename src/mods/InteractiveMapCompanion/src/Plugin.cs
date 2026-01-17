using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Server;
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

    private ModConfig? _config;
    private ServiceProvider? _services;
    private Harmony? _harmony;
    private IWebSocketServer? _server;

    private void Awake()
    {
        Log = Logger;

        _config = new ModConfig(Config);
        _services = ConfigureServices();
        _harmony = new Harmony(PluginInfo.GUID);

        // Start WebSocket server
        _server = _services.GetRequiredService<IWebSocketServer>();
        _server.Start();

        // TODO: Configure patches when implemented
        // _harmony.PatchAll();

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private ServiceProvider ConfigureServices()
    {
        var services = new ServiceCollection();

        services.AddSingleton(_config!);
        services.AddSingleton(Log);
        services.AddSingleton<IWebSocketServer, WebSocketServer>();

        // TODO: Register additional services as they are implemented
        // services.AddSingleton<IEntityTracker, EntityTrackerAdapter>();
        // services.AddSingleton<IStateManager, StateManager>();

        return services.BuildServiceProvider();
    }

    private void OnDestroy()
    {
        _server?.Stop();
        _harmony?.UnpatchSelf();
        _services?.Dispose();
    }
}

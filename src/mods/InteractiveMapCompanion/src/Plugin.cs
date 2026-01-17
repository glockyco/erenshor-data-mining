using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using InteractiveMapCompanion.Config;
using InteractiveMapCompanion.Entities;
using InteractiveMapCompanion.Server;
using InteractiveMapCompanion.State;
using Microsoft.Extensions.DependencyInjection;
using UnityEngine.SceneManagement;

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
    private IBroadcastLoop? _broadcastLoop;

    private void Awake()
    {
        Log = Logger;

        _config = new ModConfig(Config);
        _services = ConfigureServices();
        _harmony = new Harmony(PluginInfo.GUID);

        // Start WebSocket server
        _server = _services.GetRequiredService<IWebSocketServer>();
        _server.Start();

        // Get broadcast loop for Update calls
        _broadcastLoop = _services.GetRequiredService<IBroadcastLoop>();

        // Subscribe to scene changes
        SceneManager.sceneLoaded += OnSceneLoaded;

        // Initialize with current scene
        var currentScene = SceneManager.GetActiveScene().name;
        _broadcastLoop.OnSceneLoaded(currentScene);

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
    }

    private void Update()
    {
        _broadcastLoop?.Tick(UnityEngine.Time.deltaTime);
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        _broadcastLoop?.OnSceneLoaded(scene.name);
    }

    private ServiceProvider ConfigureServices()
    {
        var services = new ServiceCollection();

        // Configuration and logging
        services.AddSingleton(_config!);
        services.AddSingleton(Log);

        // Entity tracking components
        services.AddSingleton<IEntityFinder, EntityFinder>();
        services.AddSingleton<IEntityClassifier, EntityClassifier>();
        services.AddSingleton<IEntityExtractor, EntityExtractor>();

        // Track all entity types
        services.AddSingleton<Func<EntityType, bool>>(_ => true);

        services.AddSingleton<IEntityTracker, EntityTrackerAdapter>();

        // WebSocket server
        services.AddSingleton<IWebSocketServer, WebSocketServer>();

        // Broadcast loop with configurable logging
        services.AddSingleton<IBroadcastLoop>(sp =>
        {
            var config = sp.GetRequiredService<ModConfig>();
            return new BroadcastLoop(
                sp.GetRequiredService<IEntityTracker>(),
                sp.GetRequiredService<IWebSocketServer>(),
                config,
                msg =>
                {
                    // Only log if ModLogLevel is Debug
                    if (config.ModLogLevel.Value == InteractiveMapCompanion.Config.LogLevel.Debug)
                        Log.LogDebug(msg);
                }
            );
        });

        return services.BuildServiceProvider();
    }

    private void OnDestroy()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        _server?.Stop();
        _harmony?.UnpatchSelf();
        _services?.Dispose();
    }
}

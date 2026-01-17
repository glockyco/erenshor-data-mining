using BepInEx.Configuration;

namespace InteractiveMapCompanion.Config;

/// <summary>
/// BepInEx configuration for the Interactive Map Companion mod.
/// </summary>
public class ModConfig
{
    public ConfigEntry<int> Port { get; }
    public ConfigEntry<int> UpdateInterval { get; }
    public ConfigEntry<bool> EnableSpawnTracking { get; }
    public ConfigEntry<bool> EnableThirdPartyMarkers { get; }
    public ConfigEntry<bool> EnableBidirectional { get; }

    public ModConfig(ConfigFile config)
    {
        Port = config.Bind(
            "Server",
            "Port",
            18584,
            "WebSocket server port. Clients connect to ws://localhost:{port}"
        );

        UpdateInterval = config.Bind(
            "Server",
            "UpdateInterval",
            100,
            "Interval in milliseconds between state broadcasts to clients"
        );

        EnableSpawnTracking = config.Bind(
            "Features",
            "EnableSpawnTracking",
            true,
            "Track enemy deaths and broadcast respawn timers"
        );

        EnableThirdPartyMarkers = config.Bind(
            "Features",
            "EnableThirdPartyMarkers",
            true,
            "Allow other mods to register custom markers via the API"
        );

        EnableBidirectional = config.Bind(
            "Features",
            "EnableBidirectional",
            true,
            "Accept messages from clients (waypoints, pings, commands)"
        );
    }

    /// <summary>
    /// Returns the list of enabled capabilities based on current configuration.
    /// </summary>
    public string[] GetCapabilities()
    {
        var capabilities = new List<string> { "entities" };

        if (EnableSpawnTracking.Value)
            capabilities.Add("spawns");

        if (EnableThirdPartyMarkers.Value)
            capabilities.Add("markers");

        if (EnableBidirectional.Value)
            capabilities.Add("bidirectional");

        return capabilities.ToArray();
    }
}

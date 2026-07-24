#nullable enable

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SQLite;
using UnityEngine;
using Object = UnityEngine.Object;

/// <summary>
/// Asset scanner channel used by one export listener registration.
/// </summary>
public enum ExportScanChannel
{
    Null,
    GameObject,
    ScriptableObject,
    Component,
}

/// <summary>
/// Services shared by listener registration actions during one export.
/// </summary>
public sealed class ExportListenerRegistrationContext
{
    internal ExportListenerRegistrationContext(AssetScanner scanner, SQLiteConnection database)
    {
        Scanner = scanner;
        Database = database;
        CharacterKeyResolver = new CharacterStableKeyResolver();
        ZoneLineKeyResolver = new ZoneLineStableKeyResolver();
    }

    public AssetScanner Scanner { get; }
    public SQLiteConnection Database { get; }
    public CharacterStableKeyResolver CharacterKeyResolver { get; }
    public ZoneLineStableKeyResolver ZoneLineKeyResolver { get; }

    /// <summary>
    /// The dynamic-spawn listener created by the spawnpoints registration action.
    /// Null when spawnpoints was not selected.
    /// </summary>
    public DynamicSpawnSourceListener? DynamicSpawnListener { get; internal set; }

    public void RegisterNullListener(IAssetScanListener<Object> listener) => Scanner.RegisterNullListener(listener);
    public void RegisterGameObjectListener(IAssetScanListener<GameObject> listener) => Scanner.RegisterGameObjectListener(listener);
    public void RegisterComponentListener<T>(IAssetScanListener<T> listener) where T : Component => Scanner.RegisterComponentListener(listener);
    public void RegisterScriptableObjectListener<T>(IAssetScanListener<T> listener) where T : ScriptableObject => Scanner.RegisterScriptableObjectListener(listener);
}

/// <summary>
/// One ordered export listener declaration.
///
/// The ordered list in <see cref="ExportListenerRegistry.Definitions"/> is the
/// only listener inventory. Dependencies are validated against that order before
/// any registration action runs.
/// </summary>
public sealed class ExportListenerDefinition
{
    public ExportListenerDefinition(
        string key,
        string label,
        ExportScanChannel channel,
        IEnumerable<string> dependencies,
        Action<ExportListenerRegistrationContext> register)
    {
        if (string.IsNullOrWhiteSpace(key)) throw new ArgumentException("Listener key must be nonblank.", nameof(key));
        if (string.IsNullOrWhiteSpace(label)) throw new ArgumentException("Listener label must be nonblank.", nameof(label));

        Key = key;
        Label = label;
        Channel = channel;
        Dependencies = dependencies.ToArray();
        Register = register ?? throw new ArgumentNullException(nameof(register));
    }

    public string Key { get; }
    public string Label { get; }
    public ExportScanChannel Channel { get; }
    public IReadOnlyList<string> Dependencies { get; }
    public Action<ExportListenerRegistrationContext> Register { get; }
}

public sealed class ExportListenerRegistrationResult
{
    internal ExportListenerRegistrationResult(int registeredCount, DynamicSpawnSourceListener? dynamicSpawnListener)
    {
        RegisteredCount = registeredCount;
        DynamicSpawnListener = dynamicSpawnListener;
    }

    public int RegisteredCount { get; }
    public DynamicSpawnSourceListener? DynamicSpawnListener { get; }
}

/// <summary>
/// Single ordered inventory consumed by batch and editor export entrypoints.
/// </summary>
public static class ExportListenerRegistry
{
    private static readonly IReadOnlyList<ExportListenerDefinition> _definitions =
        new List<ExportListenerDefinition>
        {
            new("gameconstants", "Game Constants", ExportScanChannel.Null, Array.Empty<string>(),
                context => context.RegisterNullListener(new GameConstantListener(context.Database))),
            new("teleportlocs", "Teleport Locations", ExportScanChannel.Null, Array.Empty<string>(),
                context => context.RegisterNullListener(new TeleportLocListener(context.Database))),

            new("secretpassages", "Secret Passages", ExportScanChannel.GameObject, Array.Empty<string>(),
                context => context.RegisterGameObjectListener(new SecretPassageListener(context.Database))),
            new("wishingwells", "Wishing Wells", ExportScanChannel.GameObject, Array.Empty<string>(),
                context => context.RegisterGameObjectListener(new WishingWellListener(context.Database))),
            new("questactivations", "Quest Activations", ExportScanChannel.GameObject, Array.Empty<string>(),
                context => context.RegisterGameObjectListener(new QuestActivationListener(
                    context.Database, context.ZoneLineKeyResolver, context.CharacterKeyResolver))),

            new("ascensions", "Ascensions", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new AscensionListener(context.Database))),
            new("books", "Books", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new BookListener(context.Database))),
            new("classes", "Classes", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new ClassListener(context.Database))),
            new("quests", "Quests", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new QuestListener(context.Database))),
            new("skills", "Skills", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new SkillListener(context.Database, context.CharacterKeyResolver))),
            new("spells", "Spells", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new SpellListener(context.Database, context.CharacterKeyResolver))),
            new("stances", "Stances", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new StanceListener(context.Database))),
            new("guildtopics", "Guild Topics", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new GuildTopicListener(context.Database))),
            new("worldfactions", "World Factions", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new WorldFactionListener(context.Database))),
            new("zoneatlasentries", "Zone Atlas Entries", ExportScanChannel.ScriptableObject, Array.Empty<string>(),
                context => context.RegisterScriptableObjectListener(new ZoneAtlasEntryListener(context.Database))),
            new("items", "Items", ExportScanChannel.ScriptableObject, new[] { "spells" },
                context => context.RegisterScriptableObjectListener(new ItemListener(context.Database))),

            new("achievementtriggers", "Achievement Triggers", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new AchievementTriggerListener(context.Database))),
            new("doors", "Doors", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new DoorListener(context.Database))),
            new("forges", "Forges", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new ForgeListener(context.Database))),
            new("itembags", "Item Bags", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new ItemBagListener(context.Database))),
            new("classstartingitems", "Class Starting Items", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new ClassStartingItemsListener(context.Database))),
            new("loottables", "Loot Tables", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new LootTableListener(context.Database, context.CharacterKeyResolver))),
            new("arenarounds", "Arena Rounds", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new VithArenaListener(context.Database, context.CharacterKeyResolver))),
            new("itemdrops", "Item Drops", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new MiscListener(context.Database))),
            new("miningnodes", "Mining Nodes", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new MiningNodeListener(context.Database))),
            new("spawnpoints", "Spawn Points", ExportScanChannel.Component, Array.Empty<string>(),
                context =>
                {
                    // Registration order is significant: classic spawn points and
                    // trigger encounters must precede dynamic spawn source scanning.
                    context.RegisterComponentListener(new SpawnPointListener(context.Database, context.CharacterKeyResolver));
                    context.RegisterComponentListener(new SpawnPointTriggerListener(context.Database, context.CharacterKeyResolver));

                    string catalogPath = Path.Combine(Application.dataPath, "Editor", "ExportSystem", "AssetScanner", "dynamic-spawn-catalog.toml");
                    Debug.Log($"[DynamicSpawn] Catalog path: {catalogPath}, exists: {File.Exists(catalogPath)}");
                    DynamicSpawnCatalog catalog = DynamicSpawnCatalog.Load(catalogPath);
                    Debug.Log($"[DynamicSpawn] Catalog loaded: {catalog.Entries.Count} entries, {catalog.KnownScripts.Count} scripts");
                    context.DynamicSpawnListener = new DynamicSpawnSourceListener(context.Database, context.CharacterKeyResolver, catalog);
                    context.RegisterComponentListener(context.DynamicSpawnListener);
                }),
            new("treasurehunting", "Treasure Hunting", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new TreasureHuntingListener(context.Database))),
            new("treasurelocs", "Treasure Locations", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new TreasureLocListener(context.Database))),
            new("waters", "Waters", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new WaterListener(context.Database))),
            new("zoneannounces", "Zones", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new ZoneAnnounceListener(context.Database))),
            new("zonelines", "Zone Lines", ExportScanChannel.Component, Array.Empty<string>(),
                context => context.RegisterComponentListener(new ZoneLineListener(context.Database, context.ZoneLineKeyResolver))),
            new("characters", "Characters", ExportScanChannel.Component, new[] { "spawnpoints" },
                context => context.RegisterComponentListener(new CharacterListener(context.Database, context.CharacterKeyResolver))),
        }.AsReadOnly();

    public static IReadOnlyList<ExportListenerDefinition> Definitions => _definitions;

    public static ExportListenerRegistrationResult Register(
        AssetScanner scanner,
        SQLiteConnection database,
        IEnumerable<string> requestedKeys,
        Action<ExportListenerDefinition>? onRegistered = null)
    {
        ExportListenerRegistrationContext context = new(scanner, database);
        IReadOnlyList<ExportListenerDefinition> selected = Select(requestedKeys);

        foreach (ExportListenerDefinition definition in selected)
        {
            try
            {
                definition.Register(context);
                onRegistered?.Invoke(definition);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[EXPORT_ERROR] Failed to register listener '{definition.Key}': {ex.Message}");
                throw;
            }
        }

        return new ExportListenerRegistrationResult(selected.Count, context.DynamicSpawnListener);
    }

    public static IReadOnlyList<ExportListenerDefinition> Select(IEnumerable<string> requestedKeys)
    {
        HashSet<string> requested = new(requestedKeys, StringComparer.OrdinalIgnoreCase);
        bool exportAll = requested.Count == 0;
        HashSet<string> knownKeys = Definitions.Select(definition => definition.Key).ToHashSet(StringComparer.OrdinalIgnoreCase);
        string[] unknownKeys = requested.Where(key => !knownKeys.Contains(key)).OrderBy(key => key, StringComparer.OrdinalIgnoreCase).ToArray();
        if (unknownKeys.Length > 0)
        {
            throw new ArgumentException($"Unknown listener keys: {string.Join(", ", unknownKeys)}. Available keys: {string.Join(", ", Definitions.Select(definition => definition.Key))}");
        }

        HashSet<string> selectedKeys = exportAll ? knownKeys : requested;
        ValidateDefinitions(Definitions, selectedKeys);
        return Definitions.Where(definition => selectedKeys.Contains(definition.Key)).ToArray();
    }

    public static void ValidateDefinitions(
        IReadOnlyList<ExportListenerDefinition> definitions,
        ISet<string>? selectedKeys = null)
    {
        HashSet<string> knownKeys = definitions.Select(definition => definition.Key).ToHashSet(StringComparer.OrdinalIgnoreCase);
        HashSet<string> seen = new(StringComparer.OrdinalIgnoreCase);
        foreach (ExportListenerDefinition definition in definitions)
        {
            if (!seen.Add(definition.Key))
                throw new InvalidOperationException($"Duplicate listener key: {definition.Key}");

            foreach (string dependency in definition.Dependencies)
            {
                if (!knownKeys.Contains(dependency))
                    throw new InvalidOperationException($"Listener '{definition.Key}' depends on unknown key '{dependency}'.");
                if (selectedKeys != null && selectedKeys.Contains(definition.Key) && !selectedKeys.Contains(dependency))
                    throw new InvalidOperationException($"Listener '{definition.Key}' requires selected dependency '{dependency}'.");
                if (!seen.Contains(dependency))
                    throw new InvalidOperationException($"Listener '{definition.Key}' depends on '{dependency}', which is ordered later.");
            }
        }
    }
}

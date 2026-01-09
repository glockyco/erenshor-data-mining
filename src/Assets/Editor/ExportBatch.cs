#nullable enable

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;
using Debug = UnityEngine.Debug;

/// <summary>
/// Batch mode entry point for Unity's asset export system.
/// Enables headless export of game data to SQLite database via Unity CLI.
///
/// Usage:
/// <code>
/// Unity -batchmode -quit \
///   -projectPath /path/to/project \
///   -executeMethod ExportBatch.Run \
///   -dbPath /path/to/output.sqlite \
///   -entities items,spells,characters \
///   -logLevel verbose
/// </code>
///
/// Command-line arguments:
/// - `-dbPath <path>`: Database output path (required)
/// - `-entities <list>`: Comma-separated entity types to export (optional, default: all)
/// - `-logLevel <level>`: Logging verbosity - quiet, normal, verbose (optional, default: normal)
///
/// Available entity types:
/// achievementtriggers, ascensions, books, characters, classes, doors, forges,
/// guildtopics, itembags, items, loottables, miningnodes, quests, secretpassages,
/// skills, spells, spawnpoints, stances, teleportlocs, treasurehunting, treasurelocs,
/// waters, wishingwells, worldfactions, zoneannounces, zoneatlasentries, zonelines
///
/// Exit codes:
/// - 0: Success
/// - 1: Error (check Unity log for details)
/// </summary>
public static class ExportBatch
{
    /// <summary>
    /// Logging level for batch export operations.
    /// </summary>
    private enum LogLevel
    {
        Quiet,   // Only errors and critical messages
        Normal,  // Standard progress and completion messages
        Verbose  // Detailed progress for every phase and milestone
    }

    /// <summary>
    /// Main entry point for batch mode export.
    /// Called by Unity via -executeMethod ExportBatch.Run
    /// </summary>
    public static void Run()
    {
        Stopwatch totalStopwatch = Stopwatch.StartNew();

        try
        {
            // Parse command-line arguments
            CommandLineArgs args = ParseCommandLineArguments();

            Log(LogLevel.Normal, args.logLevel, "[EXPORT_START] Starting batch export...");
            Log(LogLevel.Normal, args.logLevel, $"[EXPORT_CONFIG] Database path: {args.dbPath}");
            Log(LogLevel.Normal, args.logLevel, $"[EXPORT_CONFIG] Entities: {(args.entityTypes.Count == 0 ? "all" : string.Join(", ", args.entityTypes))}");
            Log(LogLevel.Normal, args.logLevel, $"[EXPORT_CONFIG] Log level: {args.logLevel}");

            // Validate database path
            ValidateDatabasePath(args.dbPath);

            // Create scanner and database connection
            AssetScanner scanner = new AssetScanner();

            using (SQLiteConnection db = new SQLiteConnection(args.dbPath, SQLiteOpenFlags.ReadWrite | SQLiteOpenFlags.Create))
            {
                // Enable foreign key constraints
                db.Execute("PRAGMA foreign_keys = ON");

                // Clear shared Coordinates table before export
                // Each listener will repopulate its category during the scan
                db.CreateTable<CoordinateRecord>();
                db.DeleteAll<CoordinateRecord>();

                // Register listeners based on entity selection
                int registeredCount = RegisterListeners(scanner, db, args.entityTypes, args.logLevel);

                if (registeredCount == 0)
                {
                    throw new InvalidOperationException("No listeners were registered. Check entity type names.");
                }

                Log(LogLevel.Normal, args.logLevel, $"[EXPORT_CONFIG] Registered {registeredCount} entity types");

                // Execute scan synchronously
                ExecuteScanSynchronously(scanner, args.logLevel);

                totalStopwatch.Stop();
                Log(LogLevel.Normal, args.logLevel, $"[EXPORT_COMPLETE] Export completed successfully in {totalStopwatch.Elapsed.TotalSeconds:F2}s");
            } // Database connection automatically disposed here

            // Exit with success code
            EditorApplication.Exit(0);
        }
        catch (Exception ex)
        {
            totalStopwatch.Stop();
            Debug.LogError($"[EXPORT_ERROR] Export failed after {totalStopwatch.Elapsed.TotalSeconds:F2}s: {ex.Message}");
            Debug.LogError($"[EXPORT_STACKTRACE] {ex.StackTrace}");

            // Log inner exception if present
            if (ex.InnerException != null)
            {
                Debug.LogError($"[EXPORT_INNER_ERROR] {ex.InnerException.Message}");
                Debug.LogError($"[EXPORT_INNER_STACKTRACE] {ex.InnerException.StackTrace}");
            }

            // Exit with error code
            EditorApplication.Exit(1);
        }
    }

    /// <summary>
    /// Container for parsed command-line arguments.
    /// </summary>
    private struct CommandLineArgs
    {
        public string dbPath;
        public HashSet<string> entityTypes;
        public LogLevel logLevel;
    }

    /// <summary>
    /// Parses Unity command-line arguments for export configuration.
    /// </summary>
    /// <returns>Parsed command-line arguments</returns>
    /// <exception cref="ArgumentException">If required arguments are missing or invalid</exception>
    private static CommandLineArgs ParseCommandLineArguments()
    {
        string[] args = Environment.GetCommandLineArgs();
        CommandLineArgs result = new CommandLineArgs
        {
            dbPath = string.Empty,
            entityTypes = new HashSet<string>(StringComparer.OrdinalIgnoreCase),
            logLevel = LogLevel.Normal
        };

        for (int i = 0; i < args.Length - 1; i++)
        {
            switch (args[i])
            {
                case "-dbPath":
                    result.dbPath = args[i + 1];
                    i++;
                    break;

                case "-entities":
                    string entitiesArg = args[i + 1].Trim().ToLowerInvariant();
                    // Special case: "all" means export all entity types (leave set empty)
                    if (entitiesArg != "all")
                    {
                        string[] entities = entitiesArg.Split(new[] { ',', ' ' }, StringSplitOptions.RemoveEmptyEntries);
                        foreach (string entity in entities)
                        {
                            result.entityTypes.Add(entity.Trim());
                        }
                    }
                    i++;
                    break;

                case "-logLevel":
                    string logLevelStr = args[i + 1].ToLowerInvariant();
                    result.logLevel = logLevelStr switch
                    {
                        "quiet" => LogLevel.Quiet,
                        "normal" => LogLevel.Normal,
                        "verbose" => LogLevel.Verbose,
                        _ => throw new ArgumentException($"Invalid log level: {args[i + 1]}. Valid options: quiet, normal, verbose")
                    };
                    i++;
                    break;
            }
        }

        // Validate required arguments
        if (string.IsNullOrEmpty(result.dbPath))
        {
            throw new System.ArgumentException(
                "[EXPORT_ERROR] Missing required argument: -dbPath\n" +
                "Usage: Unity -batchmode -projectPath <path> -executeMethod ExportBatch.ExportToDatabase -dbPath <path>"
            );
        }

        return result;
    }

    /// <summary>
    /// Validates that the database path is writable.
    /// Creates parent directories if they don't exist.
    /// </summary>
    /// <param name="dbPath">Database file path to validate</param>
    /// <exception cref="InvalidOperationException">If path is invalid or not writable</exception>
    private static void ValidateDatabasePath(string dbPath)
    {
        try
        {
            string? directory = Path.GetDirectoryName(dbPath);

            if (string.IsNullOrEmpty(directory))
            {
                throw new InvalidOperationException($"Invalid database path: {dbPath}");
            }

            // Create directory if it doesn't exist
            if (!Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
                Debug.Log($"[EXPORT_INFO] Created directory: {directory}");
            }

            // Test write access by creating/opening the file
            using (FileStream fs = new FileStream(dbPath, FileMode.OpenOrCreate, FileAccess.Write))
            {
                // File is writable
            }
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Cannot write to database path '{dbPath}': {ex.Message}", ex);
        }
    }

    /// <summary>
    /// Registers listeners based on entity type selection.
    /// If entityTypes is empty, registers all listeners.
    /// </summary>
    /// <param name="scanner">AssetScanner to register listeners with</param>
    /// <param name="db">SQLite database connection</param>
    /// <param name="entityTypes">Set of entity types to export (empty = all)</param>
    /// <param name="logLevel">Current logging level</param>
    /// <returns>Number of listeners registered</returns>
    private static int RegisterListeners(AssetScanner scanner, SQLiteConnection db, HashSet<string> entityTypes, LogLevel logLevel)
    {
        bool exportAll = entityTypes.Count == 0;
        int registeredCount = 0;

        // Define all available listeners with their type keys
        // Using a dictionary for O(1) lookup and cleaner registration logic
        var listenerRegistry = new Dictionary<string, Action>
        {
            // Null listeners (no asset type, special processing)
            ["teleportlocs"] = () => scanner.RegisterNullListener(new TeleportLocListener(db)),

            // GameObject listeners
            ["secretpassages"] = () => scanner.RegisterGameObjectListener(new SecretPassageListener(db)),
            ["wishingwells"] = () => scanner.RegisterGameObjectListener(new WishingWellListener(db)),

            // ScriptableObject listeners (order matters for dependencies!)
            ["ascensions"] = () => scanner.RegisterScriptableObjectListener(new AscensionListener(db)),
            ["books"] = () => scanner.RegisterScriptableObjectListener(new BookListener(db)),
            ["classes"] = () => scanner.RegisterScriptableObjectListener(new ClassListener(db)),
            ["quests"] = () => scanner.RegisterScriptableObjectListener(new QuestListener(db)),
            ["skills"] = () => scanner.RegisterScriptableObjectListener(new SkillListener(db)),
            ["spells"] = () => scanner.RegisterScriptableObjectListener(new SpellListener(db)),
            ["stances"] = () => scanner.RegisterScriptableObjectListener(new StanceListener(db)),
            ["guildtopics"] = () => scanner.RegisterScriptableObjectListener(new GuildTopicListener(db)),
            ["worldfactions"] = () => scanner.RegisterScriptableObjectListener(new WorldFactionListener(db)),
            ["zoneatlasentries"] = () => scanner.RegisterScriptableObjectListener(new ZoneAtlasEntryListener(db)),

            // Items depend on spells (for proc data), so register after spells
            ["items"] = () => scanner.RegisterScriptableObjectListener(new ItemListener(db)),

            // Component listeners
            ["achievementtriggers"] = () => scanner.RegisterComponentListener(new AchievementTriggerListener(db)),
            ["doors"] = () => scanner.RegisterComponentListener(new DoorListener(db)),
            ["forges"] = () => scanner.RegisterComponentListener(new ForgeListener(db)),
            ["itembags"] = () => scanner.RegisterComponentListener(new ItemBagListener(db)),
            ["loottables"] = () => scanner.RegisterComponentListener(new LootTableListener(db)),
            ["miningnodes"] = () => scanner.RegisterComponentListener(new MiningNodeListener(db)),
            ["spawnpoints"] = () => scanner.RegisterComponentListener(new SpawnPointListener(db)),
            ["treasurehunting"] = () => scanner.RegisterComponentListener(new TreasureHuntingListener(db)),
            ["treasurelocs"] = () => scanner.RegisterComponentListener(new TreasureLocListener(db)),
            ["waters"] = () => scanner.RegisterComponentListener(new WaterListener(db)),
            ["zoneannounces"] = () => scanner.RegisterComponentListener(new ZoneAnnounceListener(db)),
            ["zonelines"] = () => scanner.RegisterComponentListener(new ZoneLineListener(db)),

            // Characters depend on spawn points (for IsUnique calculation), so register last
            ["characters"] = () => scanner.RegisterComponentListener(new CharacterListener(db)),
        };

        // Register listeners based on selection
        foreach (var entry in listenerRegistry)
        {
            bool shouldRegister = exportAll || entityTypes.Contains(entry.Key);

            if (shouldRegister)
            {
                try
                {
                    entry.Value(); // Execute registration action
                    registeredCount++;
                    Log(LogLevel.Verbose, logLevel, $"[EXPORT_REGISTER] Registered listener: {entry.Key}");
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[EXPORT_ERROR] Failed to register listener '{entry.Key}': {ex.Message}");
                    throw;
                }
            }
        }

        // Validate that all requested entity types were recognized
        if (!exportAll)
        {
            var unknownTypes = entityTypes.Except(listenerRegistry.Keys, StringComparer.OrdinalIgnoreCase).ToList();
            if (unknownTypes.Count > 0)
            {
                throw new ArgumentException($"Unknown entity types: {string.Join(", ", unknownTypes)}. Available types: {string.Join(", ", listenerRegistry.Keys.OrderBy(k => k))}");
            }
        }

        return registeredCount;
    }

    /// <summary>
    /// Executes the asset scan synchronously (no coroutines, no yielding).
    /// This is suitable for batch mode where we don't need editor responsiveness.
    /// </summary>
    /// <param name="scanner">AssetScanner to execute</param>
    /// <param name="logLevel">Current logging level</param>
    private static void ExecuteScanSynchronously(AssetScanner scanner, LogLevel logLevel)
    {
        Stopwatch phaseStopwatch = Stopwatch.StartNew();
        string? currentPhase = null;
        int totalSteps = 0;
        int currentStep = 0;
        int lastLoggedStep = 0;

        // Progress callback for tracking scan progress
        void ProgressCallback(AssetScanProgress progress)
        {
            // Log phase changes
            if (progress.Phase != currentPhase)
            {
                if (currentPhase != null)
                {
                    Log(LogLevel.Normal, logLevel,
                        $"[EXPORT_PHASE_COMPLETE] {currentPhase} completed in {phaseStopwatch.Elapsed.TotalSeconds:F2}s");
                }

                currentPhase = progress.Phase;
                totalSteps = progress.Total;
                currentStep = 0;
                lastLoggedStep = 0;
                phaseStopwatch.Restart();

                Log(LogLevel.Normal, logLevel, $"[EXPORT_PHASE] {currentPhase} ({totalSteps} items)");
            }

            // Update progress
            currentStep = progress.Current;

            // Log progress at milestones (verbose mode: every 100 items, normal mode: every 500 items)
            int logInterval = logLevel == LogLevel.Verbose ? 100 : 500;
            if (currentStep - lastLoggedStep >= logInterval || currentStep == totalSteps)
            {
                float percent = totalSteps > 0 ? (float)currentStep / totalSteps * 100 : 0;
                Log(LogLevel.Verbose, logLevel,
                    $"[EXPORT_PROGRESS] {currentStep}/{totalSteps} ({percent:F1}%)");
                lastLoggedStep = currentStep;
            }
        }

        // Create the scan coroutine
        var enumerator = scanner.ScanAllAssetsCoroutine(
            cancelRequested: () => false,  // Never cancel in batch mode
            progressCallback: ProgressCallback
        );

        // Execute entire coroutine synchronously by iterating to completion
        // The coroutine yields periodically for editor responsiveness,
        // but in batch mode we can just iterate through without yielding
        while (enumerator.MoveNext())
        {
            // Continue iterating - no need to yield in batch mode
        }

        // Log final phase completion
        if (currentPhase != null)
        {
            Log(LogLevel.Normal, logLevel,
                $"[EXPORT_PHASE_COMPLETE] {currentPhase} completed in {phaseStopwatch.Elapsed.TotalSeconds:F2}s");
        }
    }

    /// <summary>
    /// Logs a message if it meets the current log level threshold.
    /// </summary>
    /// <param name="messageLevel">Minimum log level required to display this message</param>
    /// <param name="currentLevel">Current log level setting</param>
    /// <param name="message">Message to log</param>
    private static void Log(LogLevel messageLevel, LogLevel currentLevel, string message)
    {
        // Log if current level is >= message level (Quiet=0, Normal=1, Verbose=2)
        if (currentLevel >= messageLevel)
        {
            Debug.Log(message);
        }
    }
}

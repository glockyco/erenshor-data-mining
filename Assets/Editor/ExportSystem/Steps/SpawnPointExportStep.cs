using System;
using System.Collections.Generic;
using System.IO; // Required for Path
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public class SpawnPointExportStep : IExportStep
{
    // --- Metadata ---
    public string StepName => "Spawn Points";
    public float ProgressWeight => 2.5f; // Scene loading can be slow

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(SpawnPointDBRecord);
        yield return typeof(SpawnPointCharacterDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        reporter.Report(0f, "Finding scenes in build settings...");

        // --- Data Fetching (Scene Paths) ---
        string[] scenePaths = EditorBuildSettings.scenes
                                .Where(s => s.enabled)
                                .Select(s => s.path)
                                .ToArray();
        int totalScenes = scenePaths.Length;
        string originalScenePath = EditorSceneManager.GetActiveScene().path; // Store current scene

        if (totalScenes == 0)
        {
            reporter.Report(1f, "No enabled scenes found in build settings.");
            return;
        }

        reporter.Report(0.02f, $"Found {totalScenes} scenes. Processing...");
        await Task.Yield();

        // --- Processing & DB Interaction (Scene by Scene) ---
        int scenesProcessed = 0;
        int totalSpawnPointCount = 0;
        int totalSpawnLinkCount = 0;

        // Ensure original scene is restored even if errors occur
        try
        {
            for (int i = 0; i < totalScenes; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();

                string currentScenePath = scenePaths[i];
                Scene currentScene = default;
                var spawnPointRecords = new List<SpawnPointDBRecord>();
                var spawnLinkRecords = new List<SpawnPointCharacterDBRecord>();

                try // Inner try for individual scene processing
                {
                    // --- Scene Loading (Unity API - Must be on main thread implicitly) ---
                    // Save changes if needed before switching? Optional.
                    // EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo();
                    reporter.Report((float)scenesProcessed / totalScenes, $"Loading scene: {Path.GetFileNameWithoutExtension(currentScenePath)}...");
                    await Task.Yield(); // Allow UI update before scene load

                    currentScene = EditorSceneManager.OpenScene(currentScenePath, OpenSceneMode.Single);
                    if (!currentScene.IsValid() || !currentScene.isLoaded)
                    {
                        Debug.LogWarning($"Could not load scene: {currentScenePath}. Skipping.");
                        scenesProcessed++; // Increment processed count even if skipped
                        continue; // Skip to next scene
                    }

                    // --- Data Extraction (Unity API - FindObjectsOfType) ---
                    SpawnPoint[] spawnPointsInScene = GameObject.FindObjectsOfType<SpawnPoint>();
                    var seenIdsInScene = new HashSet<string>(); // Track IDs *within this scene*

                    foreach (SpawnPoint sp in spawnPointsInScene)
                    {
                        // Calculate the base ID
                        string baseId = currentScene.name + sp.transform.position.ToString(); // Simple ID based on scene and position
                        string finalId = baseId;
                        int suffixCounter = 2;

                        // Ensure the ID is unique within this scene's batch
                        while (!seenIdsInScene.Add(finalId))
                        {
                            finalId = $"{baseId}_{suffixCounter++}";
                        }
                        if (finalId != baseId) Debug.LogWarning($"Duplicate position detected for SpawnPoint '{sp.gameObject.name}' in scene '{currentScene.name}' at {sp.transform.position}. Assigning modified ID: '{finalId}'");


                        var spRecord = new SpawnPointDBRecord
                        {
                            Id = finalId, // Use the final, unique ID
                            SceneName = currentScene.name,
                            SpawnDelay = sp.SpawnDelay,
                            RareNPCChance = sp.RareNPCChance,
                            LevelMod = sp.levelMod,
                            RandomWanderRange = sp.RandomWanderRange,
                            LoopPatrol = sp.LoopPatrol,
                            NightSpawn = sp.NightSpawn,
                            SpawnUponQuestCompleteQuestDBName = sp.SpawnUponQuestComplete?.DBName,
                            StopIfQuestCompleteQuestDBNames = sp.StopIfQuestComplete?.Count > 0
                                ? string.Join(",", sp.StopIfQuestComplete.Where(q => q != null).Select(q => q.DBName)) // Added null check for quests
                                : null,
                            ProtectorName = (sp.Protector != null) ? sp.Protector.name : null,
                            Staggerable = sp.staggerable,
                            StaggerMod = sp.staggerMod,
                            RotationY = sp.transform.eulerAngles.y
                        };
                        spRecord.SetPosition(sp.transform.position); // Use helper
                        spawnPointRecords.Add(spRecord);

                        // --- Export Character Links (Using helper) ---
                        int commonCount = sp.CommonSpawns?.Count ?? 0;
                        int rareCount = sp.RareSpawns?.Count ?? 0;
                        ProcessSpawnList(sp.CommonSpawns, finalId, "Common", spawnLinkRecords, sp.RareNPCChance, commonCount, rareCount);
                        ProcessSpawnList(sp.RareSpawns, finalId, "Rare", spawnLinkRecords, sp.RareNPCChance, commonCount, rareCount);
                    }

                    // --- Database Insertion (Transaction per scene) ---
                    if (spawnPointRecords.Count > 0 || spawnLinkRecords.Count > 0)
                    {
                        db.RunInTransaction(() =>
                        {
                            if (spawnPointRecords.Count > 0) db.InsertAll(spawnPointRecords); // Assuming Id is PK
                            if (spawnLinkRecords.Count > 0) db.InsertAll(spawnLinkRecords); // Assuming composite PK or no conflicts
                        });
                        totalSpawnPointCount += spawnPointRecords.Count;
                        totalSpawnLinkCount += spawnLinkRecords.Count;
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error processing scene {currentScenePath}: {ex.Message}\n{ex.StackTrace}");
                    // Optionally continue to the next scene or rethrow to stop the export
                    // throw; // Uncomment to stop export on scene error
                }
                finally
                {
                    scenesProcessed++; // Increment processed count here after try/catch/finally
                    // --- Progress Reporting (After each scene) ---
                    float progress = (float)scenesProcessed / totalScenes;
                    reporter.Report(progress, $"Processed {scenesProcessed}/{totalScenes} scenes ({totalSpawnPointCount} points, {totalSpawnLinkCount} links)...");
                    await Task.Yield(); // Allow UI update between scenes
                }
            } // End scene loop
        }
        finally // --- Scene Restoration ---
        {
            // Always try to restore the original scene
            if (!string.IsNullOrEmpty(originalScenePath) && EditorSceneManager.GetActiveScene().path != originalScenePath)
            {
                reporter.Report(1.0f, $"Restoring original scene: {Path.GetFileNameWithoutExtension(originalScenePath)}...");
                await Task.Yield(); // Allow UI update before scene load
                EditorSceneManager.OpenScene(originalScenePath);
            }
            else if (string.IsNullOrEmpty(originalScenePath) && !string.IsNullOrEmpty(EditorSceneManager.GetActiveScene().path))
            {
                // If original was untitled, maybe open a new empty scene?
                // reporter.Report(1.0f, "Opening new empty scene...");
                // await Task.Yield();
                // EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects);
            }
             // Final status update after potential scene restoration
             reporter.Report(1.0f, $"Finished exporting {totalSpawnPointCount} points, {totalSpawnLinkCount} links from {scenesProcessed} scenes.");
        }
    }

    // Helper to process CommonSpawns or RareSpawns lists (Adapted from SpawnPointExporter)
    private void ProcessSpawnList(
        List<GameObject> spawnList,
        string spawnPointId,
        string spawnType, // "Common" or "Rare"
        List<SpawnPointCharacterDBRecord> linkRecords,
        int rareNpcChance, // The SpawnPoint's RareNPCChance (0-100)
        int totalCommonCount, // Total number of common prefabs in the SpawnPoint's list
        int totalRareCount)   // Total number of rare prefabs in the SpawnPoint's list
    {
        if (spawnList == null) return;

        for (int i = 0; i < spawnList.Count; i++)
        {
            GameObject prefab = spawnList[i];
            if (prefab == null) continue;

            // --- Calculate Spawn Chance based on exact SpawnPoint.SpawnNPC logic ---
            float chance = 0.0f;
            float rareRollChance = rareNpcChance / 100.0f;
            float commonRollChance = 1.0f - rareRollChance;

            if (totalRareCount > 0) // Corresponds to the first `if (RareSpawns.Count > 0)` in SpawnNPC
            {
                if (spawnType == "Rare")
                {
                    // Avoid division by zero if RareSpawns list exists but is empty (shouldn't happen with count check)
                    chance = totalRareCount > 0 ? rareRollChance / totalRareCount : 0.0f;
                }
                else // spawnType == "Common"
                {
                    if (totalCommonCount > 0) chance = commonRollChance / totalCommonCount;
                    else chance = 0.0f; // Cannot spawn common if list is empty, even if rare roll fails
                }
            }
            else if (totalCommonCount > 0) // Corresponds to `else if (CommonSpawns.Count > 0)` in SpawnNPC
            {
                if (spawnType == "Common") chance = 1.0f / totalCommonCount;
                // If spawnType is "Rare", chance remains 0.0f
            }
            // If both counts are 0, chance remains 0.0f

            // Get the prefab's GUID
            if (AssetDatabase.TryGetGUIDAndLocalFileIdentifier(prefab, out string guid, out long localId))
            {
                var linkRecord = new SpawnPointCharacterDBRecord
                {
                    SpawnPointId = spawnPointId,
                    CharacterPrefabGuid = guid,
                    SpawnType = spawnType,
                    SpawnListIndex = i,
                    SpawnChance = chance // Store the calculated chance
                };
                linkRecords.Add(linkRecord);
            }
            else
            {
                Debug.LogWarning($"Could not get GUID for prefab '{prefab.name}' linked in SpawnPoint ID '{spawnPointId}'. Skipping link.", prefab);
            }
        }
    }
}

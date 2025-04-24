using System;
using System.Collections.Generic;
using System.IO;
using System.Linq; // Required for LINQ methods like Select
using SQLite;
using UnityEditor;
using UnityEditor.SceneManagement; // Required for scene management
using UnityEngine;
using UnityEngine.SceneManagement; // Required for Scene

public class SpawnPointExporter
{
    private readonly DatabaseManager _dbManager;

    public SpawnPointExporter()
    {
        _dbManager = new DatabaseManager();
    }

    // Asynchronous export specifically for SpawnPoints (can be used independently if needed)
    public void ExportSpawnPointsToDBAsync(DatabaseOperation.ProgressCallback progressCallback = null)
    {
        var state = new Dictionary<string, object>
        {
            { "stage", "init" },
            { "dbPath", Path.Combine(Application.dataPath, DatabaseOperation.DB_PATH) },
            { "db", null },
            { "scenePaths", null },
            { "sceneIndex", 0 },
            { "spawnPointCount", 0 },
            { "spawnLinkCount", 0 },
            { "totalScenes", 0 },
            { "originalScenePath", EditorSceneManager.GetActiveScene().path }, // Store original scene
            { "completed", false },
            { "progressCallback", progressCallback }
        };

        var stageOperations = new Dictionary<string, DatabaseManager.ExportOperation>
        {
            { "init", InitializeSpawnPointsDB },
            { "prepare_scenes", PrepareScenes },
            { "export_spawn_points", ExportSpawnPointsBatch } // Reusing the batch logic
        };

        _dbManager.ExportAsync(state,
            (s, callback) => _dbManager.GenericExportAsyncUpdate(s, callback, stageOperations,
                "Exported {0[spawnPointCount]} spawn points and {0[spawnLinkCount]} character links"),
            progressCallback);
    }

    // Initialize the database tables for spawn points
    public void InitializeSpawnPointsDB(SQLiteConnection db, Dictionary<string, object> state)
    {
        db.CreateTable<SpawnPointDBRecord>();
        db.CreateTable<SpawnPointCharacterDBRecord>();

        db.DeleteAll<SpawnPointDBRecord>();
        db.DeleteAll<SpawnPointCharacterDBRecord>();

        state["stage"] = "prepare_scenes";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.05f, "Spawn point tables initialized"); // Small progress step
    }

    // Get list of scenes to process
    public void PrepareScenes(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] scenePaths = EditorBuildSettings.scenes
                                .Where(s => s.enabled)
                                .Select(s => s.path)
                                .ToArray();
        state["scenePaths"] = scenePaths;
        state["totalScenes"] = scenePaths.Length;
        state["originalScenePath"] = EditorSceneManager.GetActiveScene().path; // Re-confirm original scene

        state["stage"] = "export_spawn_points";
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        callback?.Invoke(0.1f, $"Found {scenePaths.Length} scenes in build settings"); // Small progress step
    }

    // Export spawn points from a single scene (acts as a "batch")
    public void ExportSpawnPointsBatch(SQLiteConnection db, Dictionary<string, object> state)
    {
        string[] scenePaths = (string[])state["scenePaths"];
        int sceneIndex = (int)state["sceneIndex"];
        int spawnPointCount = (int)state["spawnPointCount"];
        int spawnLinkCount = (int)state["spawnLinkCount"];
        int totalScenes = (int)state["totalScenes"];
        string originalScenePath = (string)state["originalScenePath"];

        if (sceneIndex >= scenePaths.Length)
        {
            // Should not happen if called correctly, but safeguard
            state["completed"] = true;
            // Ensure original scene is restored if we somehow get here
            if (!string.IsNullOrEmpty(originalScenePath) && EditorSceneManager.GetActiveScene().path != originalScenePath)
            {
                EditorSceneManager.OpenScene(originalScenePath);
            }
            return;
        }

        string currentScenePath = scenePaths[sceneIndex];
        Scene currentScene = default; // Use default initialization

        var spawnPointRecords = new List<SpawnPointDBRecord>();
        var spawnLinkRecords = new List<SpawnPointCharacterDBRecord>();

        try
        {
            // --- Scene Loading ---
            // Save changes in the current scene if needed before switching
            // EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo(); // Optional: Prompt user
            currentScene = EditorSceneManager.OpenScene(currentScenePath, OpenSceneMode.Single);
            if (!currentScene.IsValid() || !currentScene.isLoaded)
            {
                Debug.LogWarning($"Could not load scene: {currentScenePath}. Skipping.");
                // Proceed to next scene without erroring out the whole process
                state["sceneIndex"] = sceneIndex + 1;
                UpdateSpawnPointProgress(state, 0.1f, 0.8f); // Update progress even if skipped
                return; // Go to next iteration
            }

            // --- Data Extraction ---
            SpawnPoint[] spawnPointsInScene = GameObject.FindObjectsOfType<SpawnPoint>();
            Debug.Log($"Found {spawnPointsInScene.Length} SpawnPoint components in scene '{currentScene.name}'."); // Diagnostic Log

            var seenIdsInScene = new HashSet<string>(); // Track IDs used *within this scene*

            foreach (SpawnPoint sp in spawnPointsInScene)
            {
                // Calculate the base ID
                string baseId = currentScene.name + sp.transform.position.ToString();
                string finalId = baseId;
                int suffixCounter = 2;

                // Ensure the ID is unique within this scene's batch
                while (!seenIdsInScene.Add(finalId))
                {
                    // If Add returns false, the ID exists. Generate a new one with a suffix.
                    finalId = $"{baseId}_{suffixCounter++}";
                }

                // Log a warning if the ID had to be modified
                if (finalId != baseId)
                {
                    Debug.LogWarning($"Duplicate position detected for SpawnPoint '{sp.gameObject.name}' in scene '{currentScene.name}' at {sp.transform.position}. Assigning modified ID: '{finalId}'");
                }

                var spRecord = new SpawnPointDBRecord
                {
                    Id = finalId, // Use the final, unique ID
                    SceneName = currentScene.name, // Store scene name explicitly
                    SpawnDelay = sp.SpawnDelay,
                    RareNPCChance = sp.RareNPCChance,
                    LevelMod = sp.levelMod,
                    RandomWanderRange = sp.RandomWanderRange,
                    LoopPatrol = sp.LoopPatrol,
                    NightSpawn = sp.NightSpawn,
                    SpawnUponQuestCompleteQuestDBName = sp.SpawnUponQuestComplete?.DBName,
                    StopIfQuestCompleteQuestDBNames = sp.StopIfQuestComplete?.Count > 0
                        ? string.Join(",", sp.StopIfQuestComplete.Select(q => q.DBName))
                        : null,
                    // Explicit null check for Protector before accessing its name
                    ProtectorName = (sp.Protector != null) ? sp.Protector.name : null,
                    Staggerable = sp.staggerable,
                    StaggerMod = sp.staggerMod,
                    RotationY = sp.transform.eulerAngles.y // Store Y rotation
                };
                spRecord.SetPosition(sp.transform.position); // Use helper to set position
                spawnPointRecords.Add(spRecord);

                // --- Export Character Links ---
                // Use the final, unique ID for linking
                ProcessSpawnList(sp.CommonSpawns, finalId, "Common", spawnLinkRecords);
                ProcessSpawnList(sp.RareSpawns, finalId, "Rare", spawnLinkRecords);
            }

            // --- Database Insertion (Transaction) ---
            // No filtering needed now, as all records have unique IDs for this scene
            if (spawnPointRecords.Count > 0 || spawnLinkRecords.Count > 0)
            {
                db.BeginTransaction();
                try
                {
                    db.InsertAll(spawnPointRecords);
                    db.InsertAll(spawnLinkRecords);
                    db.Commit();
                }
                catch (Exception ex)
                {
                    db.Rollback();
                    Debug.LogError($"Error inserting spawn point data for scene {currentScene.name}: {ex.Message}");
                    // Optionally re-throw or handle differently
                }
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"An error occurred processing scene {currentScenePath}: {ex.Message}\n{ex.StackTrace}");
            // Ensure transaction is rolled back if it was started and an error occurred before commit/rollback
            // Note: The SQLite-net wrapper might handle this, but explicit rollback on outer catch is safer if needed.
        }
        finally
        {
            // --- Scene Restoration ---
            // Always try to restore the original scene
            if (!string.IsNullOrEmpty(originalScenePath) && EditorSceneManager.GetActiveScene().path != originalScenePath)
            {
                 // Check if the scene we tried to load is actually the one active before trying to load original
                 // This avoids unnecessary scene loads if the process failed before loading the target scene.
                 if (currentScene.IsValid() && currentScene.path == EditorSceneManager.GetActiveScene().path)
                 {
                    EditorSceneManager.OpenScene(originalScenePath);
                 }
                 else if (string.IsNullOrEmpty(EditorSceneManager.GetActiveScene().path) && !string.IsNullOrEmpty(originalScenePath))
                 {
                     // If current scene is untitled/new, try loading original
                     EditorSceneManager.OpenScene(originalScenePath);
                 }
            }
            else if (string.IsNullOrEmpty(originalScenePath))
            {
                // If the original scene was untitled, maybe open a new empty scene?
                // EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects);
                // Or just leave it as is.
            }
        }

        // --- Update State ---
        // Counts are based on all processed records, as none are skipped
        state["sceneIndex"] = sceneIndex + 1;
        state["spawnPointCount"] = spawnPointCount + spawnPointRecords.Count;
        state["spawnLinkCount"] = spawnLinkCount + spawnLinkRecords.Count;

        // --- Progress Update ---
        // Progress reflects all processed records
        UpdateSpawnPointProgress(state, 0.1f, 0.8f); // Base progress 10%, spawn points take 80%

        // --- Completion Check ---
        if ((int)state["sceneIndex"] >= totalScenes)
        {
            state["completed"] = true;
            // Final progress report
             DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
             callback?.Invoke(1.0f, $"Finished exporting {(int)state["spawnPointCount"]} spawn points and {(int)state["spawnLinkCount"]} links from {totalScenes} scenes.");
        }
    }

    // Helper to process CommonSpawns or RareSpawns lists
    private void ProcessSpawnList(List<GameObject> spawnList, string spawnPointId, string spawnType, List<SpawnPointCharacterDBRecord> linkRecords)
    {
        if (spawnList == null) return;

        for (int i = 0; i < spawnList.Count; i++)
        {
            GameObject prefab = spawnList[i];
            if (prefab == null) continue;

            // Get the prefab's GUID
            if (AssetDatabase.TryGetGUIDAndLocalFileIdentifier(prefab, out string guid, out long localId))
            {
                var linkRecord = new SpawnPointCharacterDBRecord
                {
                    SpawnPointId = spawnPointId,
                    CharacterPrefabGuid = guid,
                    SpawnType = spawnType,
                    SpawnListIndex = i
                };
                linkRecords.Add(linkRecord);
            }
            else
            {
                Debug.LogWarning($"Could not get GUID for prefab '{prefab.name}' linked in SpawnPoint ID '{spawnPointId}'. Skipping link.", prefab);
            }
        }
    }

    // Helper to calculate and invoke progress callback
    private void UpdateSpawnPointProgress(Dictionary<string, object> state, float baseProgress, float stageWeight)
    {
        int sceneIndex = (int)state["sceneIndex"];
        int totalScenes = (int)state["totalScenes"];
        // Use the potentially updated counts from the state dictionary
        int currentSpawnPointCount = (int)state["spawnPointCount"];
        int currentSpawnLinkCount = (int)state["spawnLinkCount"];

        float progress = baseProgress + (stageWeight * (totalScenes > 0 ? (float)sceneIndex / totalScenes : 1.0f));
        DatabaseOperation.ProgressCallback callback = state["progressCallback"] as DatabaseOperation.ProgressCallback;
        // Report progress using the counts of processed records so far
        callback?.Invoke(progress, $"Processed {sceneIndex}/{totalScenes} scenes ({currentSpawnPointCount} points, {currentSpawnLinkCount} links)");
    }
}

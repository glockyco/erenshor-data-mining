using System;
using System.Collections.Generic;
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

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(SpawnPointDBRecord);
        yield return typeof(SpawnPointCharacterDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

        // --- Data Fetching ---
        string[] scenePaths = EditorBuildSettings.scenes
            .Where(s => s.enabled)
            .Select(s => s.path)
            .ToArray();
        int totalScenes = scenePaths.Length;
        string originalScenePath = EditorSceneManager.GetActiveScene().path;

        if (totalScenes == 0)
        {
            Debug.LogWarning("No enabled scenes found in build settings.");
            reportProgress(0, 0);
            return;
        }

        reportProgress(0, totalScenes);
        await Task.Yield();

        // --- Processing & DB Interaction ---
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
                    // --- Scene Loading ---
                    reportProgress(scenesProcessed, totalScenes);
                    await Task.Yield();

                    currentScene = EditorSceneManager.OpenScene(currentScenePath, OpenSceneMode.Single);
                    if (!currentScene.IsValid() || !currentScene.isLoaded)
                    {
                        Debug.LogWarning($"Could not load scene: {currentScenePath}. Skipping.");
                        scenesProcessed++;
                        continue;
                    }

                    // --- Data Extraction ---
                    SpawnPoint[] spawnPointsInScene = GameObject.FindObjectsOfType<SpawnPoint>();
                    var seenIdsInScene = new HashSet<string>();

                    foreach (SpawnPoint sp in spawnPointsInScene)
                    {
                        cancellationToken.ThrowIfCancellationRequested();

                        // Calculate the base ID
                        string baseId = currentScene.name + sp.transform.position;
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
                            Id = finalId,
                            SceneName = currentScene.name,
                            RareNPCChance = sp.RareNPCChance,
                            LevelMod = sp.levelMod,
                            SpawnDelay = sp.SpawnDelay,
                            Staggerable = sp.staggerable,
                            StaggerMod = sp.staggerMod,
                            NightSpawn = sp.NightSpawn,
                            PatrolPoints = sp.PatrolPoints != null ? string.Join(", ", sp.PatrolPoints.Select(t => t.position.ToString())) : null,
                            LoopPatrol = sp.LoopPatrol,
                            RandomWanderRange = sp.RandomWanderRange,
                            SpawnUponQuestCompleteDBName = sp.SpawnUponQuestComplete?.DBName,
                            StopIfQuestCompleteDBNames = sp.StopIfQuestComplete?.Count > 0 ? string.Join(", ", sp.StopIfQuestComplete.Where(q => q != null && !string.IsNullOrEmpty(q.DBName)).Select(q => q.DBName)) : null,
                            ProtectorName = (sp.Protector != null) ? sp.Protector.name : null,
                        };
                        spRecord.SetPosition(sp.transform.position);
                        spawnPointRecords.Add(spRecord);

                        // --- Export Character Links) ---
                        int commonCount = sp.CommonSpawns?.Count ?? 0;
                        int rareCount = sp.RareSpawns?.Count ?? 0;
                        ProcessSpawnList(sp.CommonSpawns, finalId, "Common", spawnLinkRecords, sp.RareNPCChance, commonCount, rareCount);
                        ProcessSpawnList(sp.RareSpawns, finalId, "Rare", spawnLinkRecords, sp.RareNPCChance, commonCount, rareCount);
                    }

                    // --- Database Insertion ---
                    if (spawnPointRecords.Count > 0 || spawnLinkRecords.Count > 0)
                    {
                        db.RunInTransaction(() =>
                        {
                            if (spawnPointRecords.Count > 0) db.InsertAll(spawnPointRecords);
                            if (spawnLinkRecords.Count > 0) db.InsertAll(spawnLinkRecords);
                        });
                        totalSpawnPointCount += spawnPointRecords.Count;
                        totalSpawnLinkCount += spawnLinkRecords.Count;
                    }
                }
                catch (OperationCanceledException) { throw; }
                catch (Exception ex)
                {
                    Debug.LogError($"Error processing scene {currentScenePath}: {ex.Message}\n{ex.StackTrace}");
                }
                finally
                {
                    scenesProcessed++;
                    // --- Progress Reporting (After each scene) ---
                    reportProgress(scenesProcessed, totalScenes);
                    await Task.Yield();
                }
            }
        }
        finally // --- Scene Restoration ---
        {
            // Always try to restore the original scene
            if (!string.IsNullOrEmpty(originalScenePath) && EditorSceneManager.GetActiveScene().path != originalScenePath)
            {
                reportProgress(scenesProcessed, totalScenes);
                await Task.Yield();
                EditorSceneManager.OpenScene(originalScenePath);
            }
            
            reportProgress(scenesProcessed, totalScenes); // Ensure final progress is reported
            Debug.Log($"Finished exporting {totalSpawnPointCount} points, {totalSpawnLinkCount} links from {scenesProcessed} scenes.");
        }
    }

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
                    chance = rareRollChance / totalRareCount;
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

            if (AssetDatabase.TryGetGUIDAndLocalFileIdentifier(prefab, out string guid, out long localId))
            {
                var linkRecord = new SpawnPointCharacterDBRecord
                {
                    SpawnPointId = spawnPointId,
                    CharacterPrefabGuid = guid,
                    SpawnType = spawnType,
                    SpawnListIndex = i,
                    SpawnChance = chance,
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

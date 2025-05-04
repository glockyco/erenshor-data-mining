using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public class NPCDialogExportStep : IExportStep
{
    private static readonly string[] PREFAB_SEARCH_PATHS = { "Assets/GameObject" };

    // --- Metadata ---
    public string StepName => "NPCDialogs";

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(NPCDialogDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        // --- Constants ---
        const int BATCH_SIZE = 50;

        // --- Initialization ---
        var batchRecords = new List<NPCDialogDBRecord>();
        var npcDialogCounters = new Dictionary<string, int>(); // Tracks the next index for each NPC
        int totalRecords = 0;
        int totalItemsToProcess = 0; // Combined count of prefabs + scenes
        int itemsProcessed = 0; // Combined processed count

        // Store original scene setup to restore later
        var originalSceneSetup = EditorSceneManager.GetSceneManagerSetup();

        try
        {
            // --- Phase 0: Count total items ---
            reportProgress(itemsProcessed, totalItemsToProcess);
            string[] prefabGuids = AssetDatabase.FindAssets("t:Prefab", PREFAB_SEARCH_PATHS);
            var scenePaths = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToList();
            totalItemsToProcess = prefabGuids.Length + scenePaths.Count;
            reportProgress(itemsProcessed, totalItemsToProcess);
            await Task.Yield();

            // --- Phase 1: Prefab Processing ---
            Debug.Log($"Found {prefabGuids.Length} prefabs to check for NPCDialogs.");
            for (int i = 0; i < prefabGuids.Length; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                string guid = prefabGuids[i];
                string assetPath = AssetDatabase.GUIDToAssetPath(guid);

                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
                if (prefab == null)
                {
                    itemsProcessed++;
                    reportProgress(itemsProcessed, totalItemsToProcess);
                    continue;
                }

                var dialogComponents = prefab.GetComponentsInChildren<NPCDialog>(true);
                if (dialogComponents.Length == 0)
                {
                    itemsProcessed++;
                    reportProgress(itemsProcessed, totalItemsToProcess);
                    continue;
                }

                foreach (var dialog in dialogComponents)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (dialog == null) continue;

                    NPC npcComponent = dialog.gameObject.GetComponent<NPC>();
                    NPCDialogDBRecord record = CreateRecordFromComponent(dialog, npcComponent, npcDialogCounters);
                    batchRecords.Add(record);

                    if (batchRecords.Count >= BATCH_SIZE)
                    {
                        totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, assetPath, cancellationToken);
                    }
                }

                totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, assetPath, cancellationToken);

                itemsProcessed++;
                reportProgress(itemsProcessed, totalItemsToProcess);
                if (i % 10 == 0) await Task.Yield();
            }
            Debug.Log($"Finished processing prefabs. Found {totalRecords} dialog records so far.");


            // --- Phase 2: Scene Processing ---
            Debug.Log($"Found {scenePaths.Count} enabled scenes to process.");
            for (int i = 0; i < scenePaths.Count; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                string scenePath = scenePaths[i];
                string sceneName = Path.GetFileNameWithoutExtension(scenePath);

                reportProgress(itemsProcessed, totalItemsToProcess);
                await Task.Yield();

                Scene scene;
                try
                {
                    scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
                    if (!scene.IsValid() || !scene.isLoaded)
                    {
                        Debug.LogWarning($"Skipping invalid or unloaded scene: {scenePath}");
                        itemsProcessed++;
                        continue;
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Failed to load scene '{scenePath}': {ex.Message}");
                    itemsProcessed++;
                    reportProgress(itemsProcessed, totalItemsToProcess);
                    await Task.Delay(100, cancellationToken);
                    continue;
                }

                var dialogComponents = scene
                    .GetRootGameObjects()
                    .SelectMany(go => go.GetComponentsInChildren<NPCDialog>(true))
                    .ToList();

                foreach (var dialog in dialogComponents)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (dialog == null) continue;

                    NPC npcComponent = dialog.gameObject.GetComponent<NPC>();
                    NPCDialogDBRecord record = CreateRecordFromComponent(dialog, npcComponent, npcDialogCounters);
                    batchRecords.Add(record);

                    if (batchRecords.Count >= BATCH_SIZE)
                    {
                        totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, scenePath, cancellationToken);
                    }
                }

                totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, scenePath, cancellationToken);

                itemsProcessed++;
                reportProgress(itemsProcessed, totalItemsToProcess);
                await Task.Yield();
            }

            Debug.Log($"Successfully exported {totalRecords} NPCDialog entries from {prefabGuids.Length} prefabs and {scenePaths.Count} scenes.");
            reportProgress(itemsProcessed, totalItemsToProcess);
        }
        catch (OperationCanceledException)
        {
             Debug.Log("NPCDialog export cancelled.");
             reportProgress(itemsProcessed, totalItemsToProcess);
             throw;
        }
        catch (Exception ex)
        {
            Debug.LogError($"NPCDialog export failed: {ex.Message}\n{ex.StackTrace}");
            reportProgress(itemsProcessed, totalItemsToProcess);
            throw;
        }
        finally
        {
            // --- Scene Cleanup ---
            reportProgress(itemsProcessed, totalItemsToProcess);
            await Task.Yield();
            EditorSceneManager.RestoreSceneManagerSetup(originalSceneSetup);
            Debug.Log("Restored original scene setup.");
        }
    }

    private async Task<int> InsertBatchAsync(SQLiteConnection db, List<NPCDialogDBRecord> batchRecords, int currentTotal, string sourceContext, CancellationToken cancellationToken)
    {
        if (batchRecords.Count == 0) return currentTotal;

        try
        {
            await Task.Run(() =>
            {
                db.RunInTransaction(() =>
                {
                    db.InsertAll(batchRecords);
                });
            }, cancellationToken);

            int newlyAdded = batchRecords.Count;
            batchRecords.Clear();
            return currentTotal + newlyAdded;
        }
        catch (OperationCanceledException) { throw; }
        catch (Exception ex)
        {
            Debug.LogError($"Error inserting NPCDialog batch from '{sourceContext}': {ex.Message}");
            // Consider how to handle duplicate primary keys if they occur despite the indexing logic
            // For now, re-throw to halt the process.
            throw;
        }
    }

    private NPCDialogDBRecord CreateRecordFromComponent(NPCDialog component, NPC npcComponent, Dictionary<string, int> npcDialogCounters)
    {
        var keywords = component.KeywordToActivate ?? new List<string>();
        string npcName = npcComponent != null && !string.IsNullOrEmpty(npcComponent.NPCName) ? npcComponent.NPCName : component.gameObject.name;

        // Get the next index for this NPC, defaulting to 0 if not seen before
        int dialogIndex = npcDialogCounters.TryGetValue(npcName, out int currentIndex) ? currentIndex : 0;
        npcDialogCounters[npcName] = dialogIndex + 1; // Increment for the next dialog of this NPC

        return new NPCDialogDBRecord
        {
            NPCName = npcName,
            DialogIndex = dialogIndex, // Assign the calculated index
            DialogText = component.Dialog,
            Keywords = string.Join(", ", keywords),
            GiveItemName = component.GiveItem?.ItemName,
            AssignQuestDBName = component.QuestToAssign?.DBName,
            CompleteQuestDBName = component.QuestToComplete?.DBName,
            RepeatingQuestDialog = component.RepeatingQuestDialog,
            KillSelfOnSay = component.KillMeOnSay,
            RequiredQuestDBName = component.RequireQuestComplete?.DBName,
            SpawnName = component.Spawn != null ? component.Spawn.name : null,
        };
    }
}

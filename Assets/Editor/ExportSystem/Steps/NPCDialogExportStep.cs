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
    // Define paths to search for prefabs containing NPCDialogs
    private static readonly string[] PREFAB_SEARCH_PATHS = { "Assets/GameObject" }; // Example: Search entire project. Could be {"Assets/Prefabs/NPCs"} etc.

    // --- Metadata ---
    public string StepName => "NPCDialogs";
    public float ProgressWeight => 1.5f;

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(NPCDialogDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        // --- Constants ---
        const float SCENE_PROCESSING_PROGRESS_SHARE = 0.9f; // Allocate 60% of progress to scenes
        const float PREFAB_PROCESSING_PROGRESS_SHARE = 1.0f - SCENE_PROCESSING_PROGRESS_SHARE; // Allocate 40% to prefabs
        const int BATCH_SIZE = 50; // Adjust batch size as needed

        // --- Initialization ---
        var batchRecords = new List<NPCDialogDBRecord>();
        int totalRecords = 0;
        int processedScenesCount = 0;
        int processedPrefabsCount = 0;
        int totalScenes = 0; // Initialize here
        int totalPrefabs = 0; // Initialize here
        string finalStatusMessage = "NPCDialog export finished."; // Default message

        // Store original scene setup to restore later
        var originalSceneSetup = EditorSceneManager.GetSceneManagerSetup();

        try
        {
            // --- Phase 1: Prefab Processing ---
            reporter.Report(SCENE_PROCESSING_PROGRESS_SHARE, "Finding NPCDialog prefabs...");
            await Task.Yield();

            string[] guids = AssetDatabase.FindAssets("t:Prefab", PREFAB_SEARCH_PATHS);
            totalPrefabs = guids.Length;

            if (totalPrefabs == 0)
            {
                reporter.Report(1.0f, "No NPCDialog prefabs found in specified paths.");
            }
            else
            {
                reporter.Report(SCENE_PROCESSING_PROGRESS_SHARE + 0.01f * PREFAB_PROCESSING_PROGRESS_SHARE, $"Found {totalPrefabs} prefabs. Processing prefabs...");
                await Task.Yield();

                for (int i = 0; i < totalPrefabs; i++)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    string guid = guids[i];
                    string assetPath = AssetDatabase.GUIDToAssetPath(guid);
                    // Calculate base progress for this prefab *before* potentially skipping
                    float prefabBaseProgress = SCENE_PROCESSING_PROGRESS_SHARE + ((float)processedPrefabsCount / totalPrefabs * PREFAB_PROCESSING_PROGRESS_SHARE);

                    GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
                    if (prefab == null)
                    {
                        processedPrefabsCount++; // Count as processed even if null
                        continue;
                    }

                    // Find NPCDialog components directly within the prefab asset
                    var dialogComponents = prefab.GetComponentsInChildren<NPCDialog>(true);
                    if (dialogComponents.Length == 0)
                    {
                        processedPrefabsCount++; // Count it as processed even if skipped
                        continue; // Skip prefabs without NPCDialog
                    }

                    int componentsInPrefab = dialogComponents.Length;
                    reporter.Report(prefabBaseProgress, $"Processing {componentsInPrefab} dialogs in prefab ({i + 1}/{totalPrefabs}): {prefab.name}...");
                    await Task.Yield();


                    for (int j = 0; j < componentsInPrefab; j++)
                    {
                        cancellationToken.ThrowIfCancellationRequested();
                        NPCDialog dialog = dialogComponents[j];
                        if (dialog == null) continue;

                        NPC npcComponent = dialog.gameObject.GetComponent<NPC>();
                        // Use assetPath as the identifier in the 'SceneName' field for prefabs
                        NPCDialogDBRecord record = CreateRecordFromComponent(dialog, npcComponent);
                        batchRecords.Add(record);

                        // Use the same batch insertion logic
                        if (batchRecords.Count >= BATCH_SIZE || (j == componentsInPrefab - 1 && batchRecords.Count > 0))
                        {
                           totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, assetPath, reporter, cancellationToken);
                        }

                        // --- Progress Reporting (Within Prefab) ---
                        float progressWithinPrefab = (float)(j + 1) / componentsInPrefab;
                        // Scale progress relative to overall prefab count and prefab progress share
                        float overallProgress = prefabBaseProgress + (progressWithinPrefab * PREFAB_PROCESSING_PROGRESS_SHARE / totalPrefabs);
                        reporter.Report(overallProgress, $"Processed {totalRecords} dialogs ({j+1}/{componentsInPrefab} in {prefab.name})...");
                        if (j % 10 == 0) await Task.Yield(); // Yield occasionally
                    }
                    processedPrefabsCount++;
                    // Report progress after finishing a prefab
                    reporter.Report(SCENE_PROCESSING_PROGRESS_SHARE + ((float)processedPrefabsCount / totalPrefabs * PREFAB_PROCESSING_PROGRESS_SHARE), $"Finished prefab {prefab.name}. Total dialogs: {totalRecords}.");
                    await Task.Yield();
                }
            }

            // --- Flush final prefab batch if any ---
            totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, "prefab post-processing", reporter, cancellationToken);

            // --- Phase 2: Scene Processing ---
            reporter.Report(0f, "Finding scenes in build settings...");
            await Task.Yield();

            var scenePaths = EditorBuildSettings.scenes
                .Where(s => s.enabled)
                .Select(s => s.path)
                .ToList();

            totalScenes = scenePaths.Count; // Assign totalScenes here
            if (totalScenes > 0)
            {
                reporter.Report(0.01f, $"Found {totalScenes} scenes. Processing scenes...");
                await Task.Yield();

                for (int i = 0; i < totalScenes; i++)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    string scenePath = scenePaths[i];
                    string sceneName = Path.GetFileNameWithoutExtension(scenePath);
                    float sceneBaseProgress = (float)processedScenesCount / totalScenes * SCENE_PROCESSING_PROGRESS_SHARE;
                    reporter.Report(sceneBaseProgress, $"Loading scene ({i + 1}/{totalScenes}): {sceneName}...");
                    await Task.Yield();

                    Scene scene;
                    try
                    {
                        scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
                        if (!scene.IsValid() || !scene.isLoaded)
                        {
                            Debug.LogWarning($"Skipping invalid or unloaded scene: {scenePath}");
                            processedScenesCount++;
                            continue;
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.LogError($"Failed to load scene '{scenePath}': {ex.Message}");
                        reporter.Report(sceneBaseProgress, $"Error loading scene: {scenePath}");
                        await Task.Delay(100, cancellationToken);
                        processedScenesCount++;
                        continue;
                    }

                    var dialogComponents = scene.GetRootGameObjects()
                                                .SelectMany(go => go.GetComponentsInChildren<NPCDialog>(true))
                                                .ToList();

                    int componentsInScene = dialogComponents.Count;
                    reporter.Report(sceneBaseProgress + (0.01f * SCENE_PROCESSING_PROGRESS_SHARE / totalScenes), $"Processing {componentsInScene} dialogs in {sceneName}...");
                    await Task.Yield();

                    for (int j = 0; j < componentsInScene; j++)
                    {
                        cancellationToken.ThrowIfCancellationRequested();
                        NPCDialog dialog = dialogComponents[j];
                        if (dialog == null) continue;

                        NPC npcComponent = dialog.gameObject.GetComponent<NPC>();
                        // Use sceneName for the record's SceneName field
                        NPCDialogDBRecord record = CreateRecordFromComponent(dialog, npcComponent);
                        batchRecords.Add(record);

                        if (batchRecords.Count >= BATCH_SIZE || (j == componentsInScene - 1 && batchRecords.Count > 0))
                        {
                            totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, scenePath, reporter, cancellationToken);
                        }

                        float progressWithinScene = (float)(j + 1) / componentsInScene;
                        float overallProgress = sceneBaseProgress + (progressWithinScene * SCENE_PROCESSING_PROGRESS_SHARE / totalScenes);
                        reporter.Report(overallProgress, $"Processed {totalRecords} dialogs ({j + 1}/{componentsInScene} in {sceneName})...");
                        if (j % 10 == 0) await Task.Yield();
                    }
                    processedScenesCount++;
                    reporter.Report((float)processedScenesCount / totalScenes * SCENE_PROCESSING_PROGRESS_SHARE, $"Finished scene {sceneName}. Total dialogs: {totalRecords}.");
                    await Task.Yield();
                }
            }
            else
            {
                reporter.Report(SCENE_PROCESSING_PROGRESS_SHARE, "No enabled scenes found in build settings.");
                await Task.Yield();
            }

            // --- Flush final scene batch if any ---
            totalRecords = await InsertBatchAsync(db, batchRecords, totalRecords, "scene post-processing", reporter, cancellationToken);

            finalStatusMessage = $"Successfully exported {totalRecords} NPCDialog entries from {processedScenesCount} scenes and {processedPrefabsCount} relevant prefabs.";
            reporter.Report(1.0f, finalStatusMessage);
        }
        catch (OperationCanceledException)
        {
             finalStatusMessage = "NPCDialog export cancelled.";
             reporter.Report(CalculateOverallProgress(processedScenesCount, totalScenes, processedPrefabsCount, totalPrefabs, SCENE_PROCESSING_PROGRESS_SHARE), finalStatusMessage);
             throw; // Re-throw cancellation
        }
        catch (Exception ex)
        {
            finalStatusMessage = $"NPCDialog export failed: {ex.Message}";
            Debug.LogError($"{finalStatusMessage}\n{ex.StackTrace}");
            reporter.Report(CalculateOverallProgress(processedScenesCount, totalScenes, processedPrefabsCount, totalPrefabs, SCENE_PROCESSING_PROGRESS_SHARE), finalStatusMessage);
            throw; // Re-throw exception
        }
        finally
        {
            // --- Scene Cleanup ---
            float finalProgress = CalculateOverallProgress(processedScenesCount, totalScenes, processedPrefabsCount, totalPrefabs, SCENE_PROCESSING_PROGRESS_SHARE);
            reporter.Report(Mathf.Clamp01(finalProgress), "Restoring original scene setup...");
            await Task.Yield(); // Give editor a moment
            EditorSceneManager.RestoreSceneManagerSetup(originalSceneSetup);
            reporter.Report(1.0f, $"{finalStatusMessage} (Status: { (cancellationToken.IsCancellationRequested ? "Cancelled" : (totalRecords > 0 ? "Complete" : "No dialogs found")) }).");
        }
    }

    // Helper to insert batch and handle reporting/errors
    private async Task<int> InsertBatchAsync(SQLiteConnection db, List<NPCDialogDBRecord> batchRecords, int currentTotal, string sourceContext, IProgressReporter reporter, CancellationToken cancellationToken)
    {
        if (batchRecords.Count == 0) return currentTotal;

        try
        {
            db.RunInTransaction(() =>
            {
                db.InsertAll(batchRecords); // Use InsertAll for efficiency
            });
            int newlyAdded = batchRecords.Count;
            batchRecords.Clear();
            return currentTotal + newlyAdded;
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error inserting NPCDialog batch from '{sourceContext}': {ex.Message}");
            reporter.Report(0, $"Error inserting batch: {ex.Message}"); // Report error at current progress
            await Task.Delay(100, cancellationToken); // Brief pause
            throw; // Re-throw to stop the export on error
        }
    }

     // Helper to calculate overall progress based on both phases
    private float CalculateOverallProgress(int processedScenes, int totalScenes, int processedPrefabs, int totalPrefabs, float sceneShare)
    {
        // Prevent division by zero if counts are zero
        float sceneProgress = (totalScenes > 0) ? (float)processedScenes / totalScenes : 1.0f;
        float prefabProgress = (totalPrefabs > 0) ? (float)processedPrefabs / totalPrefabs : 1.0f;
        // Ensure progress doesn't exceed 1.0f due to potential floating point inaccuracies or logic errors
        return Mathf.Clamp01((sceneProgress * sceneShare) + (prefabProgress * (1.0f - sceneShare)));
    }


    // Helper to create a DB record from a component
    // Now 'sourceIdentifier' can be a scene name or an asset path
    private NPCDialogDBRecord CreateRecordFromComponent(NPCDialog component, NPC npcComponent)
    {
        var keywords = component.KeywordToActivate ?? new List<string>();

        return new NPCDialogDBRecord
        {
            NPCName = npcComponent != null && !string.IsNullOrEmpty(npcComponent.NPCName)
                        ? npcComponent.NPCName
                        : component.gameObject.name,
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

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

public class CharacterExportStep : IExportStep
{
    private static readonly string[] PREFAB_SEARCH_PATHS = { "Assets/GameObject" };

    // --- Metadata ---
    public string StepName => "Characters";

    // --- Pre-Execution ---
    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(CharacterDBRecord);
    }

    // --- Execution ---
    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        // --- Constants ---
        const int BATCH_SIZE = 50;

        // --- Initialization ---
        var batchRecords = new List<CharacterDBRecord>();
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
            Debug.Log($"Found {prefabGuids.Length} prefabs to check for Characters.");
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

                var characterComponents = prefab.GetComponentsInChildren<Character>(true);
                if (characterComponents.Length == 0)
                {
                    itemsProcessed++;
                    reportProgress(itemsProcessed, totalItemsToProcess);
                    continue;
                }

                foreach (var character in characterComponents)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (character == null) continue;

                    CharacterDBRecord record = CreateRecordFromComponent(character, guid);
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
            Debug.Log($"Finished processing prefabs. Found {totalRecords} character records so far.");


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

                var characterComponents = scene
                    .GetRootGameObjects()
                    .SelectMany(go => go.GetComponentsInChildren<Character>(true))
                    .ToList();

                foreach (var character in characterComponents)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (character == null) continue;

                    // Skip if this is a prefab instance
                    if (PrefabUtility.IsPartOfPrefabInstance(character)) continue;

                    string sceneGuid = $"scene:{sceneName}:{character.gameObject.GetInstanceID()}";
                    CharacterDBRecord record = CreateRecordFromComponent(character, sceneGuid);
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

            Debug.Log($"Successfully exported {totalRecords} Character entries from {prefabGuids.Length} prefabs and {scenePaths.Count} scenes.");
            reportProgress(itemsProcessed, totalItemsToProcess);
        }
        catch (OperationCanceledException)
        {
            Debug.Log("Character export cancelled.");
            reportProgress(itemsProcessed, totalItemsToProcess);
            throw;
        }
        catch (Exception ex)
        {
            Debug.LogError($"Character export failed: {ex.Message}\n{ex.StackTrace}");
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

    private async Task<int> InsertBatchAsync(SQLiteConnection db, List<CharacterDBRecord> batchRecords, int currentTotal, string sourceContext, CancellationToken cancellationToken)
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
            Debug.LogError($"Error inserting Character batch from '{sourceContext}': {ex.Message}");
            throw;
        }
    }

    private CharacterDBRecord CreateRecordFromComponent(Character character, string guid)
    {
        NPC npc = character.GetComponent<NPC>();
        VendorInventory vendorInventory = character.GetComponent<VendorInventory>();
        MiningNode miningNode = character.GetComponent<MiningNode>();
        SimPlayer simPlayer = character.GetComponent<SimPlayer>();
        Stats stats = character.GetComponent<Stats>();
        
        CharacterDBRecord record = new CharacterDBRecord
        {
            Guid = guid,
            ObjectName = character.gameObject != null ? character.gameObject.name : null,
            MyWorldFaction = character.MyWorldFaction != null ? character.MyWorldFaction.FactionName : null,
            MyFaction = character.MyFaction.ToString(),
            AggroRange = character.AggroRange,
            AttackRange = character.AttackRange,
            AggressiveTowards = character.AggressiveTowards != null ? string.Join(", ", character.AggressiveTowards) : null,
            Allies = character.Allies != null ? string.Join(", ", character.Allies) : null,
            IsNPC = npc != null,
            IsSimPlayer = simPlayer != null,
            IsVendor = vendorInventory != null,
            IsMiningNode = miningNode != null,
            HasStats = stats != null,
            Invulnerable = character.Invulnerable,
            ShoutOnDeath = character.ShoutOnDeath != null ? string.Join(", ", character.ShoutOnDeath) : null,
            QuestCompleteOnDeath = character.QuestCompleteOnDeath != null ? character.QuestCompleteOnDeath.DBName : null,
            DestroyOnDeath = character.DestroyOnDeath,
        };
        
        if (npc != null)
        {
            record.NPCName = npc.NPCName;
        }
        
        if (stats != null)
        {
            record.Level = stats.Level;
            record.BaseHP = stats.BaseHP;
            record.BaseAC = stats.BaseAC;
            record.BaseMana = stats.BaseMana;
            record.BaseStr = stats.BaseStr;
            record.BaseEnd = stats.BaseEnd;
            record.BaseDex = stats.BaseDex;
            record.BaseAgi = stats.BaseAgi;
            record.BaseInt = stats.BaseInt;
            record.BaseWis = stats.BaseWis;
            record.BaseCha = stats.BaseCha;
            record.BaseRes = stats.BaseRes;
            record.BaseMR = stats.BaseMR;
            record.BaseER = stats.BaseER;
            record.BasePR = stats.BasePR;
            record.BaseVR = stats.BaseVR;
            record.RunSpeed = stats.RunSpeed;
            record.BaseLifeSteal = stats.BaseLifesteal;
            record.BaseMHAtkDelay = stats.BaseMHAtkDelay;
            record.BaseOHAtkDelay = stats.BaseOHAtkDelay;
        }

        if (vendorInventory != null)
        {
            record.VendorDesc = vendorInventory.VendorDesc;
            record.ItemsForSale = vendorInventory.ItemsForSale != null ? string.Join(", ", vendorInventory.ItemsForSale.Select(i => i.ItemName)) : null;
        }

        return record;
    }
}

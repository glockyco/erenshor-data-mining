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

public class MiningNodeExportStep : IExportStep
{
    public string StepName => "Mining Nodes";

    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        yield return typeof(MiningNodeDBRecord);
        yield return typeof(MiningNodeItemDBRecord);
    }

    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        reportProgress(0, 0);

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

        int scenesProcessed = 0;
        int totalMiningNodes = 0;
        int totalMiningNodeItems = 0;

        try
        {
            for (int i = 0; i < totalScenes; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();

                string currentScenePath = scenePaths[i];
                Scene currentScene = default;
                var miningNodeRecords = new List<MiningNodeDBRecord>();
                var miningNodeItemRecords = new List<MiningNodeItemDBRecord>();

                try
                {
                    reportProgress(scenesProcessed, totalScenes);
                    await Task.Yield();

                    currentScene = EditorSceneManager.OpenScene(currentScenePath, OpenSceneMode.Single);
                    if (!currentScene.IsValid() || !currentScene.isLoaded)
                    {
                        Debug.LogWarning($"Could not load scene: {currentScenePath}. Skipping.");
                        scenesProcessed++;
                        continue;
                    }

                    MiningNode[] miningNodesInScene = GameObject.FindObjectsOfType<MiningNode>();

                    foreach (MiningNode node in miningNodesInScene)
                    {
                        cancellationToken.ThrowIfCancellationRequested();

                        // Ensure node and transform are valid
                        if (node == null || node.transform == null)
                        {
                            Debug.LogWarning($"Skipping invalid MiningNode component in scene {currentScene.name}.");
                            continue;
                        }

                        string id = currentScene.name + node.transform.position;

                        var record = new MiningNodeDBRecord
                        {
                            Id = id,
                            SceneName = currentScene.name,
                            PositionX = node.transform.position.x,
                            PositionY = node.transform.position.y,
                            PositionZ = node.transform.position.z,
                            RespawnTime = node.RespawnTime
                        };
                        miningNodeRecords.Add(record);

                        // --- Export Item Drops ---
                        ProcessMiningNodeItems(node, id, miningNodeItemRecords);
                    }

                    if (miningNodeRecords.Count > 0 || miningNodeItemRecords.Count > 0)
                    {
                       await Task.Run(() => // Run DB operations off the main thread
                       {
                           db.RunInTransaction(() =>
                           {
                               if (miningNodeRecords.Count > 0) db.InsertAll(miningNodeRecords);
                               if (miningNodeItemRecords.Count > 0) db.InsertAll(miningNodeItemRecords);
                           });
                       }, cancellationToken);

                        totalMiningNodes += miningNodeRecords.Count;
                        totalMiningNodeItems += miningNodeItemRecords.Count;
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
                    reportProgress(scenesProcessed, totalScenes);
                    await Task.Yield();
                }
            }
        }
        finally
        {
            if (!string.IsNullOrEmpty(originalScenePath) && EditorSceneManager.GetActiveScene().path != originalScenePath)
            {
                reportProgress(scenesProcessed, totalScenes);
                await Task.Yield(); // Ensure progress is reported before scene switch
                try
                {
                    EditorSceneManager.OpenScene(originalScenePath);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Failed to restore original scene '{originalScenePath}': {ex.Message}");
                }
            }

            reportProgress(scenesProcessed, totalScenes);
            Debug.Log($"Finished exporting {totalMiningNodes} mining nodes and {totalMiningNodeItems} mining node items from {scenesProcessed} scenes.");
        }
    }

    private void ProcessMiningNodeItems(MiningNode node, string miningNodeId, List<MiningNodeItemDBRecord> itemRecords)
    {
        // Calculate drop chances based on the logic in MiningNode.Mine()
        // Legend = 96-99, Rare = 75-95, Common = 20-75, Guarantee = 0-19
        const float guaranteeChance = 20.00f; // 20 - 0 = 20
        const float commonChance = 55.00f; // 75 - 20 = 55
        const float rareChance = 21.00f; // 96 - 75 = 21
        const float legendChance = 4.00f; // 100 - 96 = 4

        // Create a dictionary to store the total drop chances for each item name
        Dictionary<string, float> itemTotalDropChances = new Dictionary<string, float>();

        // --- Calculate Total Drop Chances First ---

        // Guarantee
        Item guaranteeItem = node.guarantee ?? GameData.GM?.GuaranteeMine;
        if (guaranteeItem != null)
        {
            if (!itemTotalDropChances.ContainsKey(guaranteeItem.ItemName)) itemTotalDropChances[guaranteeItem.ItemName] = 0f;
            itemTotalDropChances[guaranteeItem.ItemName] += guaranteeChance;
        }

        // Common
        if (node.Common != null && node.Common.Count > 0)
        {
            float dropChancePerItem = commonChance / node.Common.Count;
            foreach (Item item in node.Common.Where(i => i != null)) // Filter out null items
            {
                if (!itemTotalDropChances.ContainsKey(item.ItemName)) itemTotalDropChances[item.ItemName] = 0f;
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }
        }

        // Rare
        if (node.Rare != null && node.Rare.Count > 0)
        {
            float dropChancePerItem = rareChance / node.Rare.Count;
            foreach (Item item in node.Rare.Where(i => i != null)) // Filter out null items
            {
                if (!itemTotalDropChances.ContainsKey(item.ItemName)) itemTotalDropChances[item.ItemName] = 0f;
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }
        }

        // Legend
        if (node.Legend != null && node.Legend.Count > 0)
        {
            float dropChancePerItem = legendChance / node.Legend.Count;
            foreach (Item item in node.Legend.Where(i => i != null)) // Filter out null items
            {
                if (!itemTotalDropChances.ContainsKey(item.ItemName)) itemTotalDropChances[item.ItemName] = 0f;
                itemTotalDropChances[item.ItemName] += dropChancePerItem;
            }
        }

        // --- Create Records with Rarity Indices ---
        int guaranteeIndex = 0;
        int commonIndex = 0;
        int rareIndex = 0;
        int legendIndex = 0;

        // Process guarantee item
        if (guaranteeItem != null)
        {
            var guaranteeRecord = new MiningNodeItemDBRecord
            {
                MiningNodeId = miningNodeId,
                Rarity = "Guarantee",
                RarityIndex = guaranteeIndex++,
                ItemName = guaranteeItem.ItemName,
                DropChance = guaranteeChance, // Chance for this specific slot/rarity
                TotalDropChance = itemTotalDropChances.TryGetValue(guaranteeItem.ItemName, out float totalChance) ? totalChance : 0f,
            };
            itemRecords.Add(guaranteeRecord);
        }

        // Process common items
        if (node.Common != null && node.Common.Count > 0)
        {
            float dropChancePerItem = commonChance / node.Common.Count;
            foreach (Item item in node.Common.Where(i => i != null)) // Filter out null items
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    Rarity = "Common",
                    RarityIndex = commonIndex++,
                    ItemName = item.ItemName,
                    DropChance = dropChancePerItem, // Chance for this specific slot/rarity
                    TotalDropChance = itemTotalDropChances.TryGetValue(item.ItemName, out float totalChance) ? totalChance : 0f,
                };
                itemRecords.Add(itemRecord);
            }
        }

        // Process rare items
        if (node.Rare != null && node.Rare.Count > 0)
        {
            float dropChancePerItem = rareChance / node.Rare.Count;
            foreach (Item item in node.Rare.Where(i => i != null)) // Filter out null items
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    Rarity = "Rare",
                    RarityIndex = rareIndex++,
                    ItemName = item.ItemName,
                    DropChance = dropChancePerItem, // Chance for this specific slot/rarity
                    TotalDropChance = itemTotalDropChances.TryGetValue(item.ItemName, out float totalChance) ? totalChance : 0f,
                };
                itemRecords.Add(itemRecord);
            }
        }

        // Process legend items
        if (node.Legend != null && node.Legend.Count > 0)
        {
            float dropChancePerItem = legendChance / node.Legend.Count;
            foreach (Item item in node.Legend.Where(i => i != null)) // Filter out null items
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    Rarity = "Legend",
                    RarityIndex = legendIndex++,
                    ItemName = item.ItemName,
                    DropChance = dropChancePerItem, // Chance for this specific slot/rarity
                    TotalDropChance = itemTotalDropChances.TryGetValue(item.ItemName, out float totalChance) ? totalChance : 0f,
                };
                itemRecords.Add(itemRecord);
            }
        }
    }
}

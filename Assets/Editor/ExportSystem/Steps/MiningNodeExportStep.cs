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
                        db.RunInTransaction(() =>
                        {
                            if (miningNodeRecords.Count > 0) db.InsertAll(miningNodeRecords);
                            if (miningNodeItemRecords.Count > 0) db.InsertAll(miningNodeItemRecords);
                        });
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
                await Task.Yield();
                EditorSceneManager.OpenScene(originalScenePath);
            }

            reportProgress(scenesProcessed, totalScenes);
            Debug.Log($"Finished exporting {totalMiningNodes} mining nodes and {totalMiningNodeItems} mining node items from {scenesProcessed} scenes.");
        }
    }

    private void ProcessMiningNodeItems(MiningNode node, string miningNodeId, List<MiningNodeItemDBRecord> itemRecords)
    {
        // Calculate drop chances based on the logic in MiningNode.Mine()
        // Legend = 96-99, Rare = 75-95, Common = 20-75, Guarantee = 0-19
        float guaranteeChance = 0.20f; // 20 - 0 = 20
        float commonChance = 0.55f; // 75 - 20 = 55
        float rareChance = 0.21f; // 96 - 75 = 21
        float legendChance = 0.04f; // 100 - 96 = 4

        // Create a dictionary to store the drop chances for each item
        Dictionary<string, float> itemDropChances = new Dictionary<string, float>();

        // Process guarantee item
        if (node.guarantee != null)
        {
            if (!itemDropChances.ContainsKey(node.guarantee.name))
            {
                itemDropChances[node.guarantee.name] = 0f;
            }
            itemDropChances[node.guarantee.name] += guaranteeChance;
        }
        else if (GameData.GM.GuaranteeMine != null)
        {
            if (!itemDropChances.ContainsKey(GameData.GM.GuaranteeMine.name))
            {
                itemDropChances[GameData.GM.GuaranteeMine.name] = 0f;
            }
            itemDropChances[GameData.GM.GuaranteeMine.name] += guaranteeChance;
        }

        // Process common items
        if (node.Common != null && node.Common.Count > 0)
        {
            float dropChance = commonChance / node.Common.Count;
            foreach (Item item in node.Common)
            {
                if (!itemDropChances.ContainsKey(item.name))
                {
                    itemDropChances[item.name] = 0f;
                }
                itemDropChances[item.name] += dropChance;
            }
        }

        // Process rare items
        if (node.Rare != null && node.Rare.Count > 0)
        {
            float dropChance = rareChance / node.Rare.Count;
            foreach (Item item in node.Rare)
            {
                if (!itemDropChances.ContainsKey(item.name))
                {
                    itemDropChances[item.name] = 0f;
                }
                itemDropChances[item.name] += dropChance;
            }
        }

        // Process legend items
        if (node.Legend != null && node.Legend.Count > 0)
        {
            float dropChance = legendChance / node.Legend.Count;
            foreach (Item item in node.Legend)
            {
                if (!itemDropChances.ContainsKey(item.name))
                {
                    itemDropChances[item.name] = 0f;
                }
                itemDropChances[item.name] += dropChance;
            }
        }

        // Create the MiningNodeItemDBRecord entries
        if (node.guarantee != null)
        {
            var guaranteeRecord = new MiningNodeItemDBRecord
            {
                MiningNodeId = miningNodeId,
                ItemName = node.guarantee.name,
                Rarity = "Guarantee",
                DropChance = guaranteeChance,
                TotalDropChance = itemDropChances[node.guarantee.name]
            };
            itemRecords.Add(guaranteeRecord);
        }
        else if (GameData.GM.GuaranteeMine != null)
        {
            var guaranteeRecord = new MiningNodeItemDBRecord
            {
                MiningNodeId = miningNodeId,
                ItemName = GameData.GM.GuaranteeMine.name,
                Rarity = "Guarantee",
                DropChance = guaranteeChance,
                TotalDropChance = itemDropChances[GameData.GM.GuaranteeMine.name]
            };
            itemRecords.Add(guaranteeRecord);
        }

        // Process common items
        if (node.Common != null && node.Common.Count > 0)
        {
            float dropChance = commonChance / node.Common.Count;
            foreach (Item item in node.Common)
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    ItemName = item.name,
                    Rarity = "Common",
                    DropChance = dropChance,
                    TotalDropChance = itemDropChances[item.name]
                };
                itemRecords.Add(itemRecord);
            }
        }

        // Process rare items
        if (node.Rare != null && node.Rare.Count > 0)
        {
            float dropChance = rareChance / node.Rare.Count;
            foreach (Item item in node.Rare)
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    ItemName = item.name,
                    Rarity = "Rare",
                    DropChance = dropChance,
                    TotalDropChance = itemDropChances[item.name]
                };
                itemRecords.Add(itemRecord);
            }
        }

        // Process legend items
        if (node.Legend != null && node.Legend.Count > 0)
        {
            float dropChance = legendChance / node.Legend.Count;
            foreach (Item item in node.Legend)
            {
                var itemRecord = new MiningNodeItemDBRecord
                {
                    MiningNodeId = miningNodeId,
                    ItemName = item.name,
                    Rarity = "Legend",
                    DropChance = dropChance,
                    TotalDropChance = itemDropChances[item.name]
                };
                itemRecords.Add(itemRecord);
            }
        }
    }
}

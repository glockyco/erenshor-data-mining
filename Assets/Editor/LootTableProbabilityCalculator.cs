using System.Collections.Generic;
using UnityEngine;

// Utility class for calculating loot drop probabilities
public class LootTableProbabilityCalculator
{
    private static readonly string WorldDropKey = "Any Common World Drop";

    // Calculate drop probabilities for a given loot table
    public Dictionary<string, double> CalculateDropProbabilities(LootTable lootTable)
    {
        // Gather all unique items (excluding world)
        List<Item>[] dropLists = new List<Item>[4];
        dropLists[0] = lootTable.LegendaryDrop ?? new List<Item>();
        dropLists[1] = lootTable.RareDrop ?? new List<Item>();
        dropLists[2] = lootTable.UncommonDrop ?? new List<Item>();
        dropLists[3] = lootTable.CommonDrop ?? new List<Item>();

        var allItems = new List<Item>();
        var itemIndex = new Dictionary<Item, int>();
        foreach (var list in dropLists)
        {
            foreach (var item in list)
            {
                if (item == null) continue;
                if (!itemIndex.ContainsKey(item))
                {
                    itemIndex[item] = allItems.Count;
                    allItems.Add(item);
                }
            }
        }
        int itemCount = allItems.Count;
        int worldDropIdx = itemCount; // last index for world drop

        // Precompute per-list item counts (for duplicates)
        var dropItemCounts = new List<Dictionary<Item, int>>();
        var totalEntries = new int[4];
        for (int i = 0; i < 4; ++i)
        {
            var dict = new Dictionary<Item, int>();
            var list = dropLists[i];
            if (list != null)
            {
                foreach (var item in list)
                {
                    if (item == null) continue;
                    if (!dict.ContainsKey(item)) dict[item] = 1;
                    else dict[item]++;
                }
                totalEntries[i] = list.Count;
            }
            else
            {
                totalEntries[i] = 0;
            }
            dropItemCounts.Add(dict);
        }

        // Prepare effective drop probabilities (with fall-through)
        double[] baseProbs = new double[] { 2.3, 4.7, 8.0, 55.0 }; // percentages
        double[] effectiveProbs = new double[4];
        double carry = 0.0;
        int maxNonCommon = lootTable.MaxNonCommonDrops;
        bool nonCommonAllowed = maxNonCommon > 0;

        for (int i = 0; i < 4; ++i)
        {
            bool hasItems = dropLists[i] != null && dropLists[i].Count > 0 && (i < 3 ? nonCommonAllowed : true);
            if (hasItems)
            {
                effectiveProbs[i] = baseProbs[i] + carry;
                carry = 0.0;
            }
            else
            {
                carry += baseProbs[i];
                effectiveProbs[i] = 0.0;
            }
        }

        int maxRolls = Mathf.Max(1, lootTable.MaxNumberDrops + 1);

        // DP cache: (rollIndex, nonCommonUsed, itemMask, worldDrop) -> probability
        var dp = new Dictionary<(int, int, int, bool), double[]>();

        double[] DP(int rollIndex, int nonCommonUsed, int itemMask, bool worldDrop)
        {
            var key = (rollIndex, nonCommonUsed, itemMask, worldDrop);
            if (dp.TryGetValue(key, out var cached))
                return cached;

            double[] result = new double[itemCount + 1]; // [item0, ..., itemN-1, worldDrop]

            if (rollIndex >= maxRolls)
            {
                // For each item/world, if present in mask, mark as dropped
                for (int i = 0; i < itemCount; ++i)
                    if ((itemMask & (1 << i)) != 0)
                        result[i] = 1.0;
                if (worldDrop)
                    result[worldDropIdx] = 1.0;
                dp[key] = result;
                return result;
            }

            double pSum = 0.0;

            // If non-common cap reached, only common can drop
            if (nonCommonUsed >= maxNonCommon)
            {
                if (effectiveProbs[3] > 0 && totalEntries[3] > 0)
                {
                    double pCommon = effectiveProbs[3] / 100.0;
                    double pWorld = pCommon * 0.1;
                    double pNormal = pCommon * 0.9;

                    // World drop (as a single event, not per item)
                    if (pWorld > 0)
                    {
                        var subRes = DP(rollIndex + 1, nonCommonUsed, itemMask, true);
                        for (int i = 0; i < result.Length; ++i)
                            result[i] += subRes[i] * pWorld;
                    }

                    // Normal common (duplicates allowed)
                    var commonDict = dropItemCounts[3];
                    int totalCommonEntries = totalEntries[3];
                    double pPerCommon = (totalCommonEntries > 0) ? pNormal / totalCommonEntries : 0.0;
                    foreach (var kvp in commonDict)
                    {
                        int idx = itemIndex[kvp.Key];
                        int newMask = itemMask | (1 << idx);
                        var subRes = DP(rollIndex + 1, nonCommonUsed, newMask, worldDrop);
                        for (int i = 0; i < result.Length; ++i)
                            result[i] += subRes[i] * pPerCommon * kvp.Value;
                    }
                    pSum += pCommon;
                }
            }
            else
            {
                // Otherwise, all tiers possible
                for (int tier = 0; tier < 4; ++tier)
                {
                    if (effectiveProbs[tier] > 0 && totalEntries[tier] > 0)
                    {
                        double pTier = effectiveProbs[tier] / 100.0;
                        pSum += pTier;

                        if (tier < 3) // Legendary, Rare, Uncommon: non-common (duplicates allowed)
                        {
                            var itemCounts = dropItemCounts[tier];
                            int totalEntriesTier = totalEntries[tier];
                            foreach (var kvp in itemCounts)
                            {
                                int idx = itemIndex[kvp.Key];
                                int newMask = itemMask | (1 << idx);
                                var subRes = DP(rollIndex + 1, nonCommonUsed + 1, newMask, worldDrop);
                                double pPerItem = (totalEntriesTier > 0) ? pTier * kvp.Value / totalEntriesTier : 0.0;
                                for (int i = 0; i < result.Length; ++i)
                                    result[i] += subRes[i] * pPerItem;
                            }
                        }
                        else // Common
                        {
                            // World drop (as a single event, not per item)
                            double pWorld = pTier * 0.1;
                            if (pWorld > 0)
                            {
                                var subRes = DP(rollIndex + 1, nonCommonUsed, itemMask, true);
                                for (int i = 0; i < result.Length; ++i)
                                    result[i] += subRes[i] * pWorld;
                            }

                            // Normal common (duplicates allowed)
                            var commonDict = dropItemCounts[3];
                            int totalCommonEntries = totalEntries[3];
                            double pNormal = pTier * 0.9;
                            double pPerCommon = (totalCommonEntries > 0) ? pNormal / totalCommonEntries : 0.0;
                            foreach (var kvp in commonDict)
                            {
                                int idx = itemIndex[kvp.Key];
                                int newMask = itemMask | (1 << idx);
                                var subRes = DP(rollIndex + 1, nonCommonUsed, newMask, worldDrop);
                                for (int i = 0; i < result.Length; ++i)
                                    result[i] += subRes[i] * pPerCommon * kvp.Value;
                            }
                        }
                    }
                }
            }

            // Chance to drop nothing
            double pNothing = 1.0 - pSum;
            if (pNothing > 0)
            {
                var subRes = DP(rollIndex + 1, nonCommonUsed, itemMask, worldDrop);
                for (int i = 0; i < result.Length; ++i)
                    result[i] += subRes[i] * pNothing;
            }

            dp[key] = result;
            return result;
        }

        // Start DP
        var finalResult = DP(0, 0, 0, false);

        // Map resultArr to dictionary
        var resultDict = new Dictionary<string, double>();
        for (int i = 0; i < allItems.Count; ++i)
            resultDict[allItems[i].name] = finalResult[i];

        // Only add world drop if there are any common drops
        if (lootTable.CommonDrop != null && lootTable.CommonDrop.Count > 0)
            resultDict[WorldDropKey] = finalResult[worldDropIdx];

        // GuaranteeOneDrop: add its probability (always one is chosen)
        if (lootTable.GuaranteeOneDrop != null && lootTable.GuaranteeOneDrop.Count > 0)
        {
            double p = 1.0 / lootTable.GuaranteeOneDrop.Count;
            foreach (var item in lootTable.GuaranteeOneDrop)
                if (item != null)
                {
                    if (resultDict.ContainsKey(item.name))
                        resultDict[item.name] = 1 - (1 - resultDict[item.name]) * (1 - p);
                    else
                        resultDict[item.name] = p;
                }
        }

        return resultDict;
    }
}

using System;
using System.Collections.Generic;
using UnityEngine;

// Utility class for calculating loot drop probabilities
public class LootTableProbabilityCalculator
{
    public static readonly string WorldDropKey = "A Common World Drop";

    // Calculate drop probabilities for a given loot table
    public Dictionary<string, double> CalculateDropProbabilities(LootTable lootTable)
    {
        // Gather all unique items (excluding world)
        List<Item>[] dropLists = new List<Item>[5];
        dropLists[0] = lootTable.UltraRareDrop ?? new List<Item>();
        dropLists[1] = lootTable.LegendaryDrop ?? new List<Item>();
        dropLists[2] = lootTable.RareDrop ?? new List<Item>();
        dropLists[3] = lootTable.UncommonDrop ?? new List<Item>();
        dropLists[4] = lootTable.CommonDrop ?? new List<Item>();

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
        var totalEntries = new int[5];
        for (int i = 0; i < 5; ++i)
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
        double[] baseProbs = new double[] { 0.33, 2.3, 4.7, 8.0, 55.0 }; // percentages (UltraRare, Legendary, Rare, Uncommon, Common)
        double[] effectiveProbs = new double[5];
        double carry = 0.0;
        int maxNonCommon = lootTable.MaxNonCommonDrops;
        bool nonCommonAllowed = maxNonCommon > 0;

        for (int i = 0; i < 5; ++i)
        {
            bool hasItems = dropLists[i] != null && dropLists[i].Count > 0 && (i < 4 ? nonCommonAllowed : true);
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
                if (effectiveProbs[4] > 0 && totalEntries[4] > 0)
                {
                    double pCommon = effectiveProbs[4] / 100.0;
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
                    var commonDict = dropItemCounts[4];
                    int totalCommonEntries = totalEntries[4];
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
                for (int tier = 0; tier < 5; ++tier)
                {
                    if (effectiveProbs[tier] > 0 && totalEntries[tier] > 0)
                    {
                        double pTier = effectiveProbs[tier] / 100.0;
                        pSum += pTier;

                        if (tier < 4) // UltraRare, Legendary, Rare, Uncommon: non-common (duplicates allowed)
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
                            var commonDict = dropItemCounts[4];
                            int totalCommonEntries = totalEntries[4];
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
        if (lootTable.GuaranteeOneDrop is { Count: > 0 })
        {
            var total = lootTable.GuaranteeOneDrop.Count;
            var guaranteeCounts = new Dictionary<string, int>();
            foreach (var item in lootTable.GuaranteeOneDrop)
            {
                if (item == null) continue;
                if (!guaranteeCounts.ContainsKey(item.name))
                    guaranteeCounts[item.name] = 1;
                else
                    guaranteeCounts[item.name]++;
            }
            foreach (var kvp in guaranteeCounts)
            {
                double p = (double)kvp.Value / total;
                if (resultDict.ContainsKey(kvp.Key))
                    resultDict[kvp.Key] = 1 - (1 - resultDict[kvp.Key]) * (1 - p);
                else
                    resultDict[kvp.Key] = p;
            }
        }

        if (lootTable.ActualDrops is { Count: > 0 })
        {
            foreach (var item in lootTable.ActualDrops)
            {
                resultDict[item.name] = 1;
            }
        }

        return resultDict;
    }

    // Returns: Dictionary<item name, double[]> where double[n] = probability of getting exactly n of that item per kill
    public Dictionary<string, double[]> CalculatePerItemDropCountDistributions(LootTable lootTable)
    {
        // Gather all unique items (excluding world)
        List<Item>[] dropLists = new List<Item>[5];
        dropLists[0] = lootTable.UltraRareDrop ?? new List<Item>();
        dropLists[1] = lootTable.LegendaryDrop ?? new List<Item>();
        dropLists[2] = lootTable.RareDrop ?? new List<Item>();
        dropLists[3] = lootTable.UncommonDrop ?? new List<Item>();
        dropLists[4] = lootTable.CommonDrop ?? new List<Item>();

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
        var totalEntries = new int[5];
        for (int i = 0; i < 5; ++i)
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

        double[] baseProbs = new double[] { 0.33, 2.3, 4.7, 8.0, 55.0 }; // percentages (UltraRare, Legendary, Rare, Uncommon, Common)
        double[] effectiveProbs = new double[5];
        double carry = 0.0;
        int maxNonCommon = lootTable.MaxNonCommonDrops;
        bool nonCommonAllowed = maxNonCommon > 0;

        for (int i = 0; i < 5; ++i)
        {
            bool hasItems = dropLists[i] != null && dropLists[i].Count > 0 && (i < 4 ? nonCommonAllowed : true);
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

        // For each item, we want to compute the probability distribution of getting n copies (n = 0..maxRolls)
        // We'll use DP: state = (rollIndex, nonCommonUsed)
        // For each state, we store: for each item, a probability vector of length (maxRolls+1)
        // We'll also track worldDrop as a "virtual item" at the end

        // DP cache: (rollIndex, nonCommonUsed, worldDrop) -> per-item count distributions
        var dp = new Dictionary<(int, int, bool), double[][]>();

        double[][] DP(int rollIndex, int nonCommonUsed, bool worldDrop)
        {
            var key = (rollIndex, nonCommonUsed, worldDrop);
            if (dp.TryGetValue(key, out var cached))
                return cached;

            // result[item][n] = probability of having n of item after this state
            int numItems = itemCount + 1; // +1 for world drop
            int maxCount = maxRolls + 1; // can't get more than maxRolls of any item
            double[][] result = new double[numItems][];
            for (int i = 0; i < numItems; ++i)
                result[i] = new double[maxCount];

            if (rollIndex >= maxRolls)
            {
                // Base case: no more rolls, all items have 0 additional drops
                for (int i = 0; i < numItems; ++i)
                    result[i][0] = 1.0;
                dp[key] = result;
                return result;
            }

            // Probabilities for this roll
            double[] rollProbs = new double[5];
            Array.Copy(effectiveProbs, rollProbs, 5);

            // If non-common cap reached, only common can drop
            if (nonCommonUsed >= maxNonCommon)
            {
                rollProbs[0] = rollProbs[1] = rollProbs[2] = rollProbs[3] = 0.0;
            }

            double pSum = 0.0;

            // List of possible outcomes for this roll:
            // Each outcome: (itemIdx, isWorldDrop, tier, countInTier, probability)
            var outcomes = new List<(int itemIdx, bool isWorld, double probability)>();

            // UltraRare, Legendary, Rare, Uncommon
            for (int tier = 0; tier < 4; ++tier)
            {
                if (rollProbs[tier] > 0 && totalEntries[tier] > 0)
                {
                    double pTier = rollProbs[tier] / 100.0;
                    pSum += pTier;
                    var itemCounts = dropItemCounts[tier];
                    int totalEntriesTier = totalEntries[tier];
                    foreach (var kvp in itemCounts)
                    {
                        int idx = itemIndex[kvp.Key];
                        double pItem = pTier * kvp.Value / totalEntriesTier;
                        outcomes.Add((idx, false, pItem));
                    }
                }
            }

            // Common
            if (rollProbs[4] > 0 && totalEntries[4] > 0)
            {
                double pTier = rollProbs[4] / 100.0;
                double pWorld = pTier * 0.1;
                double pNormal = pTier * 0.9;
                pSum += pTier;

                // World drop (as a single event, not per item)
                if (pWorld > 0)
                    outcomes.Add((worldDropIdx, true, pWorld));

                // Normal common (duplicates allowed)
                var commonDict = dropItemCounts[4];
                int totalCommonEntries = totalEntries[4];
                foreach (var kvp in commonDict)
                {
                    int idx = itemIndex[kvp.Key];
                    double pItem = pNormal * kvp.Value / totalCommonEntries;
                    outcomes.Add((idx, false, pItem));
                }
            }

            // Chance to drop nothing
            double pNothing = 1.0 - pSum;

            // For each possible outcome, recurse and update per-item distributions
            // We'll build up the result by convolving the distributions

            // Start with all items at 0 drops, probability 1
            // result[item][n] = probability
            // We'll accumulate into result

            // For each outcome, get the sub-distribution, then for each item, convolve
            // To avoid repeated convolutions, we can sum all possible outcomes for this roll

            // First, handle "nothing drops"
            if (pNothing > 0)
            {
                var subRes = DP(rollIndex + 1, nonCommonUsed, worldDrop);
                for (int i = 0; i < numItems; ++i)
                {
                    for (int n = 0; n < maxCount; ++n)
                        result[i][n] += subRes[i][n] * pNothing;
                }
            }

            // Now, for each possible outcome (one item drops)
            foreach (var outcome in outcomes)
            {
                int idx = outcome.itemIdx;
                bool isWorld = outcome.isWorld;
                double p = outcome.probability;
                int nextNonCommonUsed = nonCommonUsed;
                bool nextWorldDrop = worldDrop;

                if (isWorld)
                    nextWorldDrop = true;
                else if (idx < itemCount && idx >= 0 && idx < itemCount && idx >= 0 && idx < itemCount)
                {
                    // Only increment nonCommonUsed if it's a non-common drop
                    // (for ultrarare, legendary, rare, uncommon)
                    if (idx < itemCount && idx >= 0 && !isWorld && idx < itemCount)
                    {
                        // Find which tier this item is in
                        for (int tier = 0; tier < 4; ++tier)
                        {
                            if (dropLists[tier].Contains(allItems[idx]))
                            {
                                nextNonCommonUsed++;
                                break;
                            }
                        }
                    }
                }

                var subRes = DP(rollIndex + 1, nextNonCommonUsed, nextWorldDrop);

                for (int i = 0; i < numItems; ++i)
                {
                    for (int n = 0; n < maxCount; ++n)
                    {
                        // If this outcome dropped item i, increment count by 1
                        if (i == idx)
                        {
                            if (n > 0)
                                result[i][n] += subRes[i][n - 1] * p;
                        }
                        else if (isWorld && i == worldDropIdx)
                        {
                            if (n > 0)
                                result[i][n] += subRes[i][n - 1] * p;
                        }
                        else
                        {
                            result[i][n] += subRes[i][n] * p;
                        }
                    }
                }
            }

            dp[key] = result;
            return result;
        }

        // Start DP
        var finalResult = DP(0, 0, false);

        // Map resultArr to dictionary
        var resultDict = new Dictionary<string, double[]>();
        for (int i = 0; i < allItems.Count; ++i)
            resultDict[allItems[i].name] = finalResult[i];

        // Only add world drop if there are any common drops
        if (lootTable.CommonDrop != null && lootTable.CommonDrop.Count > 0)
            resultDict[WorldDropKey] = finalResult[worldDropIdx];

        // GuaranteeOneDrop: add its probability (always one is chosen)
        if (lootTable.GuaranteeOneDrop is { Count: > 0 })
        {
            var total = lootTable.GuaranteeOneDrop.Count;
            var guaranteeCounts = new Dictionary<string, int>();
            foreach (var item in lootTable.GuaranteeOneDrop)
            {
                if (item == null) continue;
                if (!guaranteeCounts.ContainsKey(item.name))
                    guaranteeCounts[item.name] = 1;
                else
                    guaranteeCounts[item.name]++;
            }

            foreach (var kvp in guaranteeCounts)
            {
                double p = (double)kvp.Value / total;
                // Convolve the guarantee with the existing distribution
                if (resultDict.TryGetValue(kvp.Key, out var dist))
                {
                    var newDist = new double[dist.Length];
                    // For each possible count n, probability is:
                    // - If n == 0: only possible if not chosen as guarantee
                    // - If n >= 1: sum of (prob of n-1 in DP) * p + (prob of n in DP) * (1-p)
                    newDist[0] = dist[0] * (1 - p);
                    for (int n = 1; n < dist.Length; ++n)
                        newDist[n] = dist[n] * (1 - p) + dist[n - 1] * p;
                    resultDict[kvp.Key] = newDist;
                }
                else
                {
                    var newDist = new double[maxRolls + 1];
                    newDist[0] = 1 - p;
                    newDist[1] = p;
                    resultDict[kvp.Key] = newDist;
                }
            }
        }

        if (lootTable.ActualDrops is { Count: > 0 })
        {
            foreach (var item in lootTable.ActualDrops)
            {
                var arr = new double[maxRolls + 1];
                arr[0] = 0;
                arr[1] = 1;
                resultDict[item.name] = arr;
            }
        }

        return resultDict;
    }

    // Helper: Compute expected value for each item
    public Dictionary<string, double> ComputeExpectedDrops(Dictionary<string, double[]> distDict)
    {
        var result = new Dictionary<string, double>();
        foreach (var kvp in distDict)
        {
            double exp = 0.0;
            var arr = kvp.Value;
            for (int n = 0; n < arr.Length; ++n)
                exp += n * arr[n];
            result[kvp.Key] = exp;
        }

        return result;
    }
}
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
        var distributions = CalculatePerItemDropCountDistributions(lootTable);
        var probabilities = new Dictionary<string, double>();
        foreach (var kvp in distributions)
        {
            probabilities[kvp.Key] = kvp.Value.Length > 0 ? 1.0 - kvp.Value[0] : 0.0;
        }

        return probabilities;
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
        int guaranteedRolls = Mathf.Max(0, lootTable.NumberOfGuaranteedDrops);
        int fixedDropCount = 0;
        if (lootTable.ActualDrops != null)
        {
            foreach (var item in lootTable.ActualDrops)
            {
                if (item != null)
                    fixedDropCount++;
            }
        }
        int maxCount = maxRolls + guaranteedRolls + fixedDropCount + 1;

        // For each item, compute the probability distribution of getting n copies.
        // Normal rolls, guaranteed rolls, and fixed ActualDrops all contribute counts.

        // DP cache: (rollIndex, nonCommonUsed, worldDrop) -> per-item count distributions
        var dp = new Dictionary<(int, int, bool), double[][]>();

        double[][] DP(int rollIndex, int nonCommonUsed, bool worldDrop)
        {
            var key = (rollIndex, nonCommonUsed, worldDrop);
            if (dp.TryGetValue(key, out var cached))
                return cached;

            // result[item][n] = probability of having n of item after this state
            int numItems = itemCount + 1; // +1 for world drop
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

        ApplyGuaranteedDropDistributions(lootTable, resultDict, maxCount);

        if (lootTable.ActualDrops is { Count: > 0 })
        {
            foreach (var item in lootTable.ActualDrops)
            {
                if (item == null) continue;
                var fixedDropDistribution = new double[maxCount];
                fixedDropDistribution[1] = 1.0;
                ConvolveDropDistribution(resultDict, item.name, fixedDropDistribution, maxCount);
            }
        }

        return resultDict;
    }

    private static void ApplyGuaranteedDropDistributions(
        LootTable lootTable,
        Dictionary<string, double[]> resultDict,
        int maxCount)
    {
        if (lootTable.GuaranteeOneDrop is not { Count: > 0 })
            return;

        int rollCount = Mathf.Max(0, lootTable.NumberOfGuaranteedDrops);
        if (rollCount <= 0)
            return;

        var items = new List<Item>();
        var itemIndexes = new Dictionary<Item, int>();
        var weights = new List<int>();
        int nullEntryCount = 0;

        foreach (var item in lootTable.GuaranteeOneDrop)
        {
            if (item == null)
            {
                nullEntryCount++;
                continue;
            }

            if (itemIndexes.TryGetValue(item, out var index))
            {
                weights[index]++;
                continue;
            }

            itemIndexes[item] = items.Count;
            items.Add(item);
            weights.Add(1);
        }

        if (items.Count == 0)
            return;

        if (items.Count > 63)
            throw new InvalidOperationException($"LootTable '{lootTable.name}' has {items.Count} distinct guaranteed items; the exporter supports at most 63.");

        ulong initialSelectedMask = 0UL;
        if (lootTable.ActualDrops != null)
        {
            foreach (var item in lootTable.ActualDrops)
            {
                if (item != null && itemIndexes.TryGetValue(item, out var index))
                    initialSelectedMask |= 1UL << index;
            }
        }

        int totalEntryCount = lootTable.GuaranteeOneDrop.Count;
        for (int itemIndex = 0; itemIndex < items.Count; itemIndex++)
        {
            var distribution = CalculateGuaranteedItemDistribution(
                itemIndex,
                items,
                weights,
                nullEntryCount,
                totalEntryCount,
                rollCount,
                initialSelectedMask,
                maxCount);
            ConvolveDropDistribution(resultDict, items[itemIndex].name, distribution, maxCount);
        }
    }

    private static double[] CalculateGuaranteedItemDistribution(
        int targetItemIndex,
        List<Item> items,
        List<int> weights,
        int nullEntryCount,
        int totalEntryCount,
        int rollCount,
        ulong initialSelectedMask,
        int maxCount)
    {
        var states = new Dictionary<(ulong selectedMask, int targetCount), double>
        {
            [(initialSelectedMask, 0)] = 1.0
        };

        for (int roll = 0; roll < rollCount; roll++)
        {
            var nextStates = new Dictionary<(ulong selectedMask, int targetCount), double>();

            foreach (var state in states)
            {
                ulong selectedMask = state.Key.selectedMask;
                int targetCount = state.Key.targetCount;
                double stateProbability = state.Value;
                int invalidEntryCount = nullEntryCount;

                for (int itemIndex = 0; itemIndex < items.Count; itemIndex++)
                {
                    if ((selectedMask & (1UL << itemIndex)) != 0)
                        invalidEntryCount += weights[itemIndex];
                }

                double invalidProbability = (double)invalidEntryCount / totalEntryCount;
                double validScale = invalidProbability >= 1.0
                    ? 0.0
                    : (1.0 - Math.Pow(invalidProbability, 10)) / (1.0 - invalidProbability);
                double fallbackScale = Math.Pow(invalidProbability, 9);

                for (int itemIndex = 0; itemIndex < items.Count; itemIndex++)
                {
                    bool alreadySelected = (selectedMask & (1UL << itemIndex)) != 0;
                    double entryProbability = (double)weights[itemIndex] / totalEntryCount;
                    double outcomeProbability = alreadySelected
                        ? fallbackScale * entryProbability
                        : validScale * entryProbability;

                    if (outcomeProbability <= 0.0)
                        continue;

                    ulong nextSelectedMask = alreadySelected ? selectedMask : selectedMask | (1UL << itemIndex);
                    int nextTargetCount = targetCount + (itemIndex == targetItemIndex ? 1 : 0);
                    AddStateProbability(nextStates, (nextSelectedMask, nextTargetCount), stateProbability * outcomeProbability);
                }

                if (nullEntryCount > 0)
                {
                    double nullOutcomeProbability = fallbackScale * nullEntryCount / totalEntryCount;
                    if (nullOutcomeProbability > 0.0)
                        AddStateProbability(nextStates, (selectedMask, targetCount), stateProbability * nullOutcomeProbability);
                }
            }

            states = nextStates;
        }

        var distribution = new double[maxCount];
        foreach (var state in states)
        {
            distribution[state.Key.targetCount] += state.Value;
        }

        return distribution;
    }

    private static void AddStateProbability(
        Dictionary<(ulong selectedMask, int targetCount), double> states,
        (ulong selectedMask, int targetCount) key,
        double probability)
    {
        if (states.ContainsKey(key))
            states[key] += probability;
        else
            states[key] = probability;
    }

    private static void ConvolveDropDistribution(
        Dictionary<string, double[]> resultDict,
        string itemName,
        double[] addedDistribution,
        int maxCount)
    {
        if (!resultDict.TryGetValue(itemName, out var existingDistribution))
        {
            resultDict[itemName] = addedDistribution;
            return;
        }

        var convolved = new double[maxCount];
        for (int existingCount = 0; existingCount < existingDistribution.Length; existingCount++)
        {
            for (int addedCount = 0; addedCount < addedDistribution.Length; addedCount++)
            {
                int combinedCount = existingCount + addedCount;
                if (combinedCount >= maxCount)
                    continue;
                convolved[combinedCount] += existingDistribution[existingCount] * addedDistribution[addedCount];
            }
        }

        resultDict[itemName] = convolved;
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

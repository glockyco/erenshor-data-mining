using System;
using System.Collections.Generic;
using UnityEngine;

// Utility class for calculating loot drop probabilities
public class LootTableProbabilityCalculator
{
    // Returns per-item count distributions at the default loot rate, without guild bonuses.
    // code-fact: loot.common_drop_tiers
    // code-fact: loot.common_world_items_substitution
    public Dictionary<string, double[]> CalculatePerItemDropCountDistributions(
        LootTableInputs lootTable,
        IReadOnlyList<LootItemInputs> commonWorldItems
    )
    {
        if (commonWorldItems == null || commonWorldItems.Count == 0)
            throw new InvalidOperationException(
                "CommonWorldItems must contain at least one entry."
            );

        List<LootItemInputs>[] dropLists =
        {
            lootTable.UltraRareDrop,
            lootTable.LegendaryDrop,
            lootTable.RareDrop,
            lootTable.UncommonDrop,
            lootTable.CommonDrop,
        };
        var allItems = new List<LootItemInputs>();
        var itemIndex = new Dictionary<LootItemInputs, int>();
        void AddItems(IEnumerable<LootItemInputs> items)
        {
            foreach (var item in items)
            {
                if (item != null && !itemIndex.ContainsKey(item))
                {
                    itemIndex[item] = allItems.Count;
                    allItems.Add(item);
                }
            }
        }
        foreach (var list in dropLists)
            AddItems(list);
        if (lootTable.CommonDrop.Count > 0)
            AddItems(commonWorldItems);

        int itemCount = allItems.Count;
        var nonCommonItemProbs = new double[itemCount];
        var commonItemProbs = new double[itemCount];
        var cappedCommonItemProbs = new double[itemCount];

        // A disabled tier falls through to the next non-empty tier. Once the
        // non-common cap is reached, all of [0,70] falls through to Common.
        double[] thresholds = { 0.33, 2.3, 7.0, 15.0, 70.0 };
        double previousThreshold = 0.0;
        double pNonCommon = 0.0;
        for (int tier = 0; tier < 4; tier++)
        {
            if (dropLists[tier].Count == 0 || lootTable.MaxNonCommonDrops <= 0)
                continue;
            double pTier = (thresholds[tier] - previousThreshold) / 100.0;
            previousThreshold = thresholds[tier];
            pNonCommon += pTier;
            foreach (var item in dropLists[tier])
            {
                // Null entries still consume a roll and the non-common cap.
                if (item != null)
                    nonCommonItemProbs[itemIndex[item]] += pTier / dropLists[tier].Count;
            }
        }

        if (lootTable.CommonDrop.Count > 0)
        {
            double pCommon = (thresholds[4] - previousThreshold) / 100.0;
            double pCappedCommon = thresholds[4] / 100.0;
            foreach (var item in lootTable.CommonDrop)
            {
                if (item == null)
                    continue;
                int index = itemIndex[item];
                commonItemProbs[index] += pCommon * 0.9 / lootTable.CommonDrop.Count;
                cappedCommonItemProbs[index] += pCappedCommon * 0.9 / lootTable.CommonDrop.Count;
            }
            foreach (var item in commonWorldItems)
            {
                if (item == null)
                    continue;
                int index = itemIndex[item];
                commonItemProbs[index] += pCommon * 0.1 / commonWorldItems.Count;
                cappedCommonItemProbs[index] += pCappedCommon * 0.1 / commonWorldItems.Count;
            }
        }

        int maxRolls = Mathf.Max(0, lootTable.MaxNumberDrops + 1);
        int maxCount =
            maxRolls
            + Mathf.Max(0, lootTable.NumberOfGuaranteedDrops)
            + lootTable.ActualDrops.Count
            + 1;
        var dp = new Dictionary<(int roll, int nonCommonUsed), double[][]>();

        double[][] DP(int roll, int nonCommonUsed)
        {
            var key = (roll, nonCommonUsed);
            if (dp.TryGetValue(key, out var cached))
                return cached;

            var result = new double[itemCount][];
            for (int i = 0; i < itemCount; i++)
                result[i] = new double[maxCount];
            if (roll >= maxRolls)
            {
                for (int i = 0; i < itemCount; i++)
                    result[i][0] = 1.0;
            }
            else
            {
                bool capped = nonCommonUsed >= lootTable.MaxNonCommonDrops;
                double pNonCommonRoll = capped ? 0.0 : pNonCommon;
                var sameCap = DP(roll + 1, nonCommonUsed);
                var nextCap = pNonCommonRoll > 0.0 ? DP(roll + 1, nonCommonUsed + 1) : null;
                for (int i = 0; i < itemCount; i++)
                {
                    double pCommonItem = capped ? cappedCommonItemProbs[i] : commonItemProbs[i];
                    double pNonCommonItem = capped ? 0.0 : nonCommonItemProbs[i];
                    // The tier that produced an outcome, not the item's list
                    // memberships, determines whether it consumes the cap.
                    for (int n = 0; n < maxCount; n++)
                    {
                        result[i][n] = sameCap[i][n] * (1.0 - pNonCommonRoll - pCommonItem);
                        if (n > 0)
                            result[i][n] += sameCap[i][n - 1] * pCommonItem;
                        if (nextCap != null)
                        {
                            result[i][n] += nextCap[i][n] * (pNonCommonRoll - pNonCommonItem);
                            if (n > 0)
                                result[i][n] += nextCap[i][n - 1] * pNonCommonItem;
                        }
                    }
                }
            }
            dp[key] = result;
            return result;
        }

        var finalResult = DP(0, 0);
        var resultDict = new Dictionary<string, double[]>();
        for (int i = 0; i < itemCount; i++)
            resultDict.Add(allItems[i].StableKey, finalResult[i]);

        ApplyGuaranteedDropDistributions(lootTable, resultDict, maxCount);
        foreach (var item in lootTable.ActualDrops)
        {
            if (item == null)
                continue;
            var fixedDropDistribution = new double[maxCount];
            fixedDropDistribution[1] = 1.0;
            ConvolveDropDistribution(resultDict, item.StableKey, fixedDropDistribution, maxCount);
        }
        return resultDict;
    }

    // Re-implements the guaranteed rolls of LootTable.InitLootTable.
    // code-fact: loot.guarantee_one_drop
    private static void ApplyGuaranteedDropDistributions(
        LootTableInputs lootTable,
        Dictionary<string, double[]> resultDict,
        int maxCount
    )
    {
        if (lootTable.GuaranteeOneDrop is not { Count: > 0 })
            return;

        int rollCount = Mathf.Max(0, lootTable.NumberOfGuaranteedDrops);
        if (rollCount <= 0)
            return;

        var items = new List<LootItemInputs>();
        var itemIndexes = new Dictionary<LootItemInputs, int>();
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
            throw new InvalidOperationException(
                $"LootTable '{lootTable.Name}' has {items.Count} distinct guaranteed items; the exporter supports at most 63."
            );

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
                maxCount
            );
            ConvolveDropDistribution(
                resultDict,
                items[itemIndex].StableKey,
                distribution,
                maxCount
            );
        }
    }

    private static double[] CalculateGuaranteedItemDistribution(
        int targetItemIndex,
        List<LootItemInputs> items,
        List<int> weights,
        int nullEntryCount,
        int totalEntryCount,
        int rollCount,
        ulong initialSelectedMask,
        int maxCount
    )
    {
        var states = new Dictionary<(ulong selectedMask, int targetCount), double>
        {
            [(initialSelectedMask, 0)] = 1.0,
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
                double validScale =
                    invalidProbability >= 1.0
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

                    ulong nextSelectedMask = alreadySelected
                        ? selectedMask
                        : selectedMask | (1UL << itemIndex);
                    int nextTargetCount = targetCount + (itemIndex == targetItemIndex ? 1 : 0);
                    AddStateProbability(
                        nextStates,
                        (nextSelectedMask, nextTargetCount),
                        stateProbability * outcomeProbability
                    );
                }

                if (nullEntryCount > 0)
                {
                    double nullOutcomeProbability =
                        fallbackScale * nullEntryCount / totalEntryCount;
                    if (nullOutcomeProbability > 0.0)
                        AddStateProbability(
                            nextStates,
                            (selectedMask, targetCount),
                            stateProbability * nullOutcomeProbability
                        );
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
        double probability
    )
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
        int maxCount
    )
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
                convolved[combinedCount] +=
                    existingDistribution[existingCount] * addedDistribution[addedCount];
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

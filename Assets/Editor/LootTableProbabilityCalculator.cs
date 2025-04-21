using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.Linq;

[CustomEditor(typeof(LootTable))]
public class LootTableProbabilityCalculator : Editor
{
    private Dictionary<object, double> dropChances = new Dictionary<object, double>();
    private bool calculated = false;
    private static readonly string WorldDropKey = "Any Common World Drop";

    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        LootTable lootTable = (LootTable)target;

        if (GUILayout.Button("Calculate Drop Probabilities"))
        {
            dropChances = CalculateDropProbabilities(lootTable);
            calculated = true;
        }

        if (calculated)
        {
            EditorGUILayout.LabelField("Per-Kill Drop Probabilities:");
            foreach (var kvp in dropChances.OrderByDescending(kvp => kvp.Value))
            {
                string label = kvp.Key is Item item ? item.name : kvp.Key.ToString();
                EditorGUILayout.LabelField($"{label}: {kvp.Value * 100:F4}%");
            }
        }
    }

    private Dictionary<object, double> CalculateDropProbabilities(LootTable lootTable)
    {
        // Gather all possible items (excluding world items)
        HashSet<Item> allItems = new HashSet<Item>();
        List<Item> guaranteeOneDrop = lootTable.GuaranteeOneDrop ?? new List<Item>();
        List<Item> commonDrop = lootTable.CommonDrop ?? new List<Item>();
        List<Item> uncommonDrop = lootTable.UncommonDrop ?? new List<Item>();
        List<Item> rareDrop = lootTable.RareDrop ?? new List<Item>();
        List<Item> legendaryDrop = lootTable.LegendaryDrop ?? new List<Item>();

        foreach (var item in guaranteeOneDrop) if (item != null) allItems.Add(item);
        foreach (var item in commonDrop) if (item != null) allItems.Add(item);
        foreach (var item in uncommonDrop) if (item != null) allItems.Add(item);
        foreach (var item in rareDrop) if (item != null) allItems.Add(item);
        foreach (var item in legendaryDrop) if (item != null) allItems.Add(item);

        // World drops: always non-empty, but not added to allItems

        Dictionary<object, double> result = new Dictionary<object, double>();
        foreach (var item in allItems)
            result[item] = 0.0;
        result[WorldDropKey] = 0.0;

        int maxRolls = Mathf.Max(1, lootTable.MaxNumberDrops + 1);
        int maxNonCommon = lootTable.MaxNonCommonDrops;
        bool nonCommonAllowed = maxNonCommon > 0;

        // Prepare drop lists (with possible duplicates)
        List<List<Item>> dropLists = new List<List<Item>>()
        {
            legendaryDrop,
            rareDrop,
            uncommonDrop,
            commonDrop
        };

        // Prepare drop probabilities (with fall-through)
        double[] baseProbs = new double[] { 2.3, 4.7, 8.0, 55.0 }; // percentages
        double[] effectiveProbs = new double[4];
        double carry = 0.0;
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

        // GuaranteeOneDrop: add its probability (always one is chosen)
        if (guaranteeOneDrop.Count > 0)
        {
            double p = 1.0 / guaranteeOneDrop.Count;
            foreach (var item in guaranteeOneDrop)
                if (item != null) result[item] += p;
        }

        // Recursive enumeration
        void Recurse(int rollIndex, int nonCommonUsed, HashSet<object> itemsSoFar, double probSoFar)
        {
            if (rollIndex >= maxRolls)
            {
                foreach (var obj in itemsSoFar.ToList())
                    result[obj] += probSoFar;
                return;
            }

            double pSum = 0.0;

            // If non-common cap reached, only common can drop
            if (nonCommonUsed >= maxNonCommon)
            {
                // Only common drop possible
                if (effectiveProbs[3] > 0 && dropLists[3] != null && dropLists[3].Count > 0)
                {
                    double pCommon = effectiveProbs[3] / 100.0;
                    double pWorld = pCommon * 0.1;
                    double pNormal = pCommon * 0.9;

                    // World drop (as a single event, not per item)
                    if (pWorld > 0)
                    {
                        var newSet = new HashSet<object>(itemsSoFar);
                        newSet.Add(WorldDropKey);
                        Recurse(rollIndex + 1, nonCommonUsed, newSet, probSoFar * pWorld);
                    }

                    // Normal common (duplicates allowed)
                    var commonItemCounts = dropLists[3].Where(x => x != null).GroupBy(x => x).ToDictionary(g => g.Key, g => g.Count());
                    int totalCommonEntries = dropLists[3].Count;
                    double pPerCommon = (totalCommonEntries > 0) ? pNormal / totalCommonEntries : 0.0;
                    foreach (var kvp in commonItemCounts)
                    {
                        var newSet = new HashSet<object>(itemsSoFar);
                        newSet.Add(kvp.Key);
                        Recurse(rollIndex + 1, nonCommonUsed, newSet, probSoFar * pPerCommon * kvp.Value);
                    }
                    pSum += pCommon;
                }
            }
            else
            {
                // Otherwise, all tiers possible
                for (int tier = 0; tier < 4; ++tier)
                {
                    if (effectiveProbs[tier] > 0 && dropLists[tier] != null && dropLists[tier].Count > 0)
                    {
                        double pTier = effectiveProbs[tier] / 100.0;
                        pSum += pTier;

                        if (tier < 3) // Legendary, Rare, Uncommon: non-common (duplicates allowed)
                        {
                            var itemCounts = dropLists[tier].Where(x => x != null).GroupBy(x => x).ToDictionary(g => g.Key, g => g.Count());
                            int totalEntries = dropLists[tier].Count;
                            foreach (var kvp in itemCounts)
                            {
                                var newSet = new HashSet<object>(itemsSoFar);
                                newSet.Add(kvp.Key);
                                double pPerItem = (totalEntries > 0) ? pTier * kvp.Value / totalEntries : 0.0;
                                Recurse(rollIndex + 1, nonCommonUsed + 1, newSet, probSoFar * pPerItem);
                            }
                        }
                        else // Common
                        {
                            // World drop (as a single event, not per item)
                            double pWorld = pTier * 0.1;
                            if (pWorld > 0)
                            {
                                var newSet = new HashSet<object>(itemsSoFar);
                                newSet.Add(WorldDropKey);
                                Recurse(rollIndex + 1, nonCommonUsed, newSet, probSoFar * pWorld);
                            }

                            // Normal common (duplicates allowed)
                            var commonItemCounts = dropLists[3].Where(x => x != null).GroupBy(x => x).ToDictionary(g => g.Key, g => g.Count());
                            int totalCommonEntries = dropLists[3].Count;
                            double pNormal = pTier * 0.9;
                            double pPerCommon = (totalCommonEntries > 0) ? pNormal / totalCommonEntries : 0.0;
                            foreach (var kvp in commonItemCounts)
                            {
                                var newSet = new HashSet<object>(itemsSoFar);
                                newSet.Add(kvp.Key);
                                Recurse(rollIndex + 1, nonCommonUsed, newSet, probSoFar * pPerCommon * kvp.Value);
                            }
                        }
                    }
                }
            }

            // Chance to drop nothing
            double pNothing = 1.0 - pSum;
            if (pNothing > 0)
                Recurse(rollIndex + 1, nonCommonUsed, new HashSet<object>(itemsSoFar), probSoFar * pNothing);
        }

        // Start recursion
        Recurse(0, 0, new HashSet<object>(), 1.0);

        // Clamp to [0,1]
        foreach (var key in result.Keys.ToList())
            result[key] = Mathf.Clamp01((float)result[key]);

        return result;
    }
}

using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

[CustomEditor(typeof(LootTable))]
public class LootTableProbabilityEditor : UnityEditor.Editor
{
    private Dictionary<string, double> _dropChances = new();
    private Dictionary<string, double[]> _perItemDistributions = new();
    private Dictionary<string, double> _expectedDrops = new();
    
    private bool _isCalculated;
    
    private readonly LootTableProbabilityCalculator _calculator = new();

    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        LootTable lootTable = (LootTable)target;

        if (GUILayout.Button("Calculate Drop Probabilities"))
        {
            _dropChances = _calculator.CalculateDropProbabilities(lootTable);
            _perItemDistributions = _calculator.CalculatePerItemDropCountDistributions(lootTable);
            _expectedDrops = _calculator.ComputeExpectedDrops(_perItemDistributions);
            _isCalculated = true;
        }

        if (_isCalculated)
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Per-Kill Drop Probabilities:");
            foreach (var kvp in _dropChances.OrderByDescending(kvp => kvp.Value))
            {
                EditorGUILayout.LabelField($"{kvp.Key}: {kvp.Value * 100:F4}%");
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Expected Number Per Kill:");
            foreach (var kvp in _expectedDrops.OrderByDescending(kvp => kvp.Value))
            {
                EditorGUILayout.LabelField($"{kvp.Key}: {kvp.Value:F4}");
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Probability of Getting Exactly n of Each Item:");
            foreach (var kvp in _perItemDistributions)
            {
                var dist = kvp.Value;
                string line = $"{kvp.Key}:";
                for (int n = 0; n < dist.Length; ++n)
                {
                    if (dist[n] > 1e-8) // Only show non-zero probabilities
                    {
                        line += $"  P({n})={dist[n] * 100:F4}%";
                    }
                }
                EditorGUILayout.LabelField(line);
            }
        }
    }
}

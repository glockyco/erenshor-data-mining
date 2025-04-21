using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.Linq;

[CustomEditor(typeof(LootTable))]
public class LootTableProbabilityEditor : Editor
{
    private Dictionary<string, double> dropChances = new Dictionary<string, double>();
    private bool calculated = false;
    private LootTableProbabilityCalculator calculator = new LootTableProbabilityCalculator();

    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        LootTable lootTable = (LootTable)target;

        if (GUILayout.Button("Calculate Drop Probabilities"))
        {
            dropChances = calculator.CalculateDropProbabilities(lootTable);
            calculated = true;
        }

        if (calculated)
        {
            EditorGUILayout.LabelField("Per-Kill Drop Probabilities:");
            foreach (var kvp in dropChances.OrderByDescending(kvp => kvp.Value))
            {
                EditorGUILayout.LabelField($"{kvp.Key}: {kvp.Value * 100:F4}%");
            }
        }
    }
}
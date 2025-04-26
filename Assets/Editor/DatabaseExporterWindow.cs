using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public class DatabaseExporterWindow : EditorWindow
{
    private MasterExporter _exporter;
    private float _progress = 0f;
    private string _status = "Ready";
    private bool _showAdvancedOptions = false;

    // Dependencies needed by steps (can be initialized here or elsewhere)
    private readonly LootTableProbabilityCalculator _probabilityCalculator = new LootTableProbabilityCalculator();

    [MenuItem("Tools/Database/Export Database")] // Keep the same menu item path
    public static void ShowWindow()
    {
        var window = GetWindow<DatabaseExporterWindow>("Database Exporter");
        window.minSize = new Vector2(400, 320); // Increased height slightly for new button
        window.Show();
    }

    // Initialize MasterExporter when the window is enabled
    private void OnEnable()
    {
        // Ensure only one instance if window is re-enabled
        if (_exporter == null)
        {
            _exporter = new MasterExporter();
        }
    }

    // Request cancellation if the window is disabled (e.g., closed) during export
    private void OnDisable()
    {
        // Check IsRunning before cancelling to avoid issues if it wasn't running
        if (_exporter != null && _exporter.IsRunning)
        {
             _exporter.CancelExport();
        }
    }

     // Final check on destruction
    private void OnDestroy()
    {
        if (_exporter != null && _exporter.IsRunning)
        {
             _exporter.CancelExport();
        }
        // Optional: Nullify exporter to release resources if needed, though GC should handle it.
        // _exporter = null;
    }

    // Draw the window UI
    private void OnGUI()
    {
        // Safety check in case OnEnable wasn't called properly
        if (_exporter == null) _exporter = new MasterExporter();

        GUILayout.Label("Database Exporter", EditorStyles.boldLabel); // Keep title simple
        EditorGUILayout.Space();

        // Display status from the UpdateProgress callback
        EditorGUILayout.LabelField("Status:", _status);
        EditorGUILayout.Space();

        // Progress bar - show only when running
        if (_exporter.IsRunning)
        {
            // Display progress and the latest status message in the bar
            EditorGUI.ProgressBar(EditorGUILayout.GetControlRect(false, 20f), _progress, $"{_status} ({_progress * 100:F0}%)");
            EditorGUILayout.Space();
        }

        // --- Buttons ---
        // Disable buttons while the exporter is running
        EditorGUI.BeginDisabledGroup(_exporter.IsRunning);

        if (GUILayout.Button("Export All Data"))
        {
            StartExport(GetAllExportSteps());
        }

        _showAdvancedOptions = EditorGUILayout.Foldout(_showAdvancedOptions, "Advanced Options");
        if (_showAdvancedOptions)
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            // Buttons for individual steps
            if (GUILayout.Button("Export Characters Only"))
            {
                StartExport(new List<IExportStep> { new CharacterExportStep() });
            }
            if (GUILayout.Button("Export Items Only"))
            {
                StartExport(new List<IExportStep> { new ItemExportStep() });
            }
            if (GUILayout.Button("Export Loot Drops Only"))
            {
                // Pass dependencies needed by the step's constructor
                StartExport(new List<IExportStep> { new LootDropExportStep(_probabilityCalculator) });
            }
            if (GUILayout.Button("Export Spawn Points Only"))
            {
                StartExport(new List<IExportStep> { new SpawnPointExportStep() });
            }
            if (GUILayout.Button("Export Spells Only"))
            {
                StartExport(new List<IExportStep> { new SpellExportStep() });
            }
            if (GUILayout.Button("Export Skills Only"))
            {
                StartExport(new List<IExportStep> { new SkillExportStep() });
            }
            if (GUILayout.Button("Export Quests Only"))
            {
                StartExport(new List<IExportStep> { new QuestExportStep() });
            }
            if (GUILayout.Button("Export Factions Only"))
            {
                StartExport(new List<IExportStep> { new FactionExportStep() });
            }

            EditorGUILayout.EndVertical();
        }

        EditorGUI.EndDisabledGroup();

        // --- Cancel Button ---
        // Show only when running
        if (_exporter.IsRunning)
        {
            EditorGUILayout.Space();
            if (GUILayout.Button("Cancel Export"))
            {
                _exporter.CancelExport(); // Call the MasterExporter's cancel method
            }
        }

        // --- DB Path Info ---
        EditorGUILayout.Space();
        // Get path from MasterExporter constant
        EditorGUILayout.LabelField("Database Path:", Path.GetFullPath(Path.Combine(Application.dataPath, MasterExporter.DB_PATH)));
    }

    // Starts the export process with the selected list of steps
    private void StartExport(List<IExportStep> steps)
    {
        // Double-check if already running before starting
        if (_exporter.IsRunning)
        {
            Debug.LogWarning("Exporter is already running. Please wait or cancel.");
            return;
        }

        _progress = 0f;
        _status = "Initializing...";
        Repaint(); // Update UI immediately to show "Initializing..."
        _exporter.StartExportAsync(steps, UpdateProgress); // Pass the steps and the UI update callback
    }

    // Defines the sequence of steps for the "Export All" button
    private List<IExportStep> GetAllExportSteps()
    {
        // Create instances of all steps in the desired execution order
        return new List<IExportStep>
        {
            new CharacterExportStep(),
            new ItemExportStep(),
            new LootDropExportStep(_probabilityCalculator),
            new SpawnPointExportStep(),
            new SpellExportStep(),
            new SkillExportStep(),
            new QuestExportStep(),
            new FactionExportStep(),
        };
    }

    // Callback method passed to MasterExporter to receive progress updates
    private void UpdateProgress(float overallProgress, string status)
    {
        _progress = overallProgress;
        _status = status;
        Repaint(); // Redraw the window to show the latest progress and status
    }
}

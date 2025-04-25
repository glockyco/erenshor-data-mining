using System.IO;
using UnityEditor;
using UnityEngine;

public class DatabaseExporterWindow : EditorWindow
{
    private bool _isExporting = false;
    private float _progress = 0f;
    private string _status = "Ready";
    private bool _showAdvancedOptions = false;

    // Create instances of exporters
    private readonly DatabaseExporter _databaseExporter;
    private readonly CharacterExporter _characterExporter;
    private readonly ItemExporter _itemExporter;
    private readonly LootDropExporter _lootDropExporter;
    private readonly SpawnPointExporter _spawnPointExporter;
    private readonly SpellExporter _spellExporter;

    public DatabaseExporterWindow()
    {
        _databaseExporter = new DatabaseExporter();
        _characterExporter = new CharacterExporter();
        _itemExporter = new ItemExporter();
        _lootDropExporter = new LootDropExporter();
        _spawnPointExporter = new SpawnPointExporter();
        _spellExporter = new SpellExporter();
    }

    [MenuItem("Tools/Database/Export Database")]
    public static void ShowWindow()
    {
        var window = GetWindow<DatabaseExporterWindow>("Database Exporter");
        // Increased min height slightly for the new button
        window.minSize = new Vector2(400, 270);
        window.Show();
    }

    private void OnGUI()
    {
        GUILayout.Label("Database Exporter", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        EditorGUILayout.LabelField("Status:", _status);
        EditorGUILayout.Space();

        // Progress bar
        if (_isExporting)
        {
            EditorGUI.ProgressBar(EditorGUILayout.GetControlRect(false, 20f), _progress, $"{_progress * 100:F0}%");
            EditorGUILayout.Space();
        }

        // Export buttons
        EditorGUI.BeginDisabledGroup(_isExporting);

        if (GUILayout.Button("Export All Data"))
        {
            StartExportAll();
        }

        _showAdvancedOptions = EditorGUILayout.Foldout(_showAdvancedOptions, "Advanced Options");

        if (_showAdvancedOptions)
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            if (GUILayout.Button("Export Characters Only"))
            {
                StartExportCharacters();
            }

            if (GUILayout.Button("Export Items Only"))
            {
                StartExportItems();
            }

            if (GUILayout.Button("Export Loot Drops Only"))
            {
                StartExportLootDrops();
            }

            if (GUILayout.Button("Export Spawn Points Only")) // <-- Add Spawn Point button
            {
                StartExportSpawnPoints();
            }

            if (GUILayout.Button("Export Spells Only"))
            {
                StartExportSpells();
            }

            EditorGUILayout.EndVertical();
        }

        EditorGUI.EndDisabledGroup();

        // Cancel button
        if (_isExporting)
        {
            EditorGUILayout.Space();
            if (GUILayout.Button("Cancel Export"))
            {
                CancelExport();
            }
        }

        // Database path info
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("Database Path:", Path.Combine(Application.dataPath, DatabaseExporter.DB_PATH));
    }

    private void StartExportAll()
    {
        _isExporting = true;
        _progress = 0f;
        _status = "Initializing...";

        _databaseExporter.ExportAllToDBAsync(UpdateProgress);
    }

    private void StartExportCharacters()
    {
        _isExporting = true;
        _progress = 0f;
        _status = "Initializing...";

        _characterExporter.ExportCharactersToDBAsync(UpdateProgress);
    }

    private void StartExportItems()
    {
        _isExporting = true;
        _progress = 0f;
        _status = "Initializing...";

        _itemExporter.ExportItemsToDBAsync(UpdateProgress);
    }

    private void StartExportLootDrops()
    {
        _isExporting = true;
        _progress = 0f;
        _status = "Initializing...";

        _lootDropExporter.ExportLootDropsToDBAsync(UpdateProgress);
    }

    private void StartExportSpawnPoints() // <-- Add handler method
    {
        _isExporting = true;
        _progress = 0f;
        _status = "Initializing...";

        _spawnPointExporter.ExportSpawnPointsToDBAsync(UpdateProgress);
    }

    private void StartExportSpells()
    {
        _isExporting = true;
        _progress = 0f;
        _status = "Initializing...";
        DatabaseOperation.ResetCancelFlag();
        _spellExporter.ExportSpellsToDBAsync(UpdateProgress);
    }


    private void CancelExport()
    {
        DatabaseExporter.CancelExport(); // Uses the static method in DatabaseOperation
        _status = "Cancelling...";
    }

    private void UpdateProgress(float progress, string status)
    {
        // Ensure updates happen on the main thread (already handled by EditorApplication.update)
        _progress = progress;
        _status = status;

        // If progress is 1.0 or more, or status indicates completion/cancellation
        if (progress >= 1.0f || status.Contains("Cancelled") || status.Contains("Exported")) // Check for final status messages
        {
             // Small delay before resetting the flag to ensure the final status is displayed
            EditorApplication.delayCall += () => {
                _isExporting = false;
                // Ensure progress shows 100% on completion if it wasn't exactly 1.0
                if (progress >= 1.0f && !status.Contains("Cancelled")) {
                    _progress = 1.0f;
                }
                Repaint(); // Final repaint after state change
            };
        } else if (status.Contains("Cancelling")) {
             // Don't immediately set _isExporting to false, wait for "Cancelled" status
        }


        // Force UI update
        Repaint();
    }

    // Ensure cleanup delegate is removed when the window is closed
    private void OnDestroy()
    {
        DatabaseOperation.CleanupDelegate();
    }
}

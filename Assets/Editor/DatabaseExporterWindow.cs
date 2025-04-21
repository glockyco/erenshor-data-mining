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

    public DatabaseExporterWindow()
    {
        _databaseExporter = new DatabaseExporter();
        _characterExporter = new CharacterExporter();
        _itemExporter = new ItemExporter();
        _lootDropExporter = new LootDropExporter();
    }

    [MenuItem("Tools/Database/Export Database")]
    public static void ShowWindow()
    {
        var window = GetWindow<DatabaseExporterWindow>("Database Exporter");
        window.minSize = new Vector2(400, 250);
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

    private void CancelExport()
    {
        DatabaseExporter.CancelExport();
        _status = "Cancelling...";
    }

    private void UpdateProgress(float progress, string status)
    {
        // Update UI from the main thread
        _progress = progress;
        _status = status;

        // If progress is 1.0, the operation is complete
        if (progress >= 1.0f)
        {
            _isExporting = false;
        }

        // Force UI update
        Repaint();
    }
}

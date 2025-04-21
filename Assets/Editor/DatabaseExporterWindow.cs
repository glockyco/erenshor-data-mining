using UnityEngine;
using UnityEditor;
using System.IO;
using System;

public class DatabaseExporterWindow : EditorWindow
{
    private Vector2 scrollPosition;
    private string statusMessage = "";
    private bool showExportOptions = true;
    private bool showExportPath = true;
    private string dbPath;

    // Progress tracking
    private bool isExporting = false;
    private float exportProgress = 0f;
    private string exportStatus = "";
    private bool showProgressBar = false;

    [MenuItem("Tools/Database Exporter")]
    public static void ShowWindow()
    {
        GetWindow<DatabaseExporterWindow>("Database Exporter");
    }

    private void OnEnable()
    {
        // Initialize the database path
        dbPath = Path.Combine(Application.dataPath, DatabaseExporter.DB_PATH);
    }

    private void OnGUI()
    {
        scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);

        GUILayout.Label("Database Exporter", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // Database path section
        showExportPath = EditorGUILayout.Foldout(showExportPath, "Database Path");
        if (showExportPath)
        {
            EditorGUI.indentLevel++;
            EditorGUILayout.LabelField("Current Path:", dbPath);
            EditorGUI.indentLevel--;
        }

        EditorGUILayout.Space();

        // Progress bar
        if (showProgressBar)
        {
            EditorGUILayout.LabelField("Export Progress:");
            EditorGUI.ProgressBar(EditorGUILayout.GetControlRect(false, 20), exportProgress, exportStatus);
            EditorGUILayout.Space();

            if (isExporting)
            {
                if (GUILayout.Button("Cancel Export", GUILayout.Height(25)))
                {
                    CancelExport();
                }
                EditorGUILayout.Space();
            }
        }

        // Export options section
        showExportOptions = EditorGUILayout.Foldout(showExportOptions, "Export Options");
        if (showExportOptions)
        {
            EditorGUI.indentLevel++;

            EditorGUI.BeginDisabledGroup(isExporting);

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Export All Data", GUILayout.Height(30)))
            {
                ExportAll();
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.Space();

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Export Characters Only", GUILayout.Height(30)))
            {
                ExportCharacters();
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.Space();

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Export Items Only", GUILayout.Height(30)))
            {
                ExportItems();
            }
            EditorGUILayout.EndHorizontal();

            EditorGUI.EndDisabledGroup();

            EditorGUI.indentLevel--;
        }

        EditorGUILayout.Space();

        // Status message
        if (!string.IsNullOrEmpty(statusMessage))
        {
            EditorGUILayout.HelpBox(statusMessage, MessageType.Info);
        }

        EditorGUILayout.EndScrollView();
    }

    private void Update()
    {
        // Repaint the window to update the progress bar
        if (isExporting)
        {
            Repaint();
        }
    }

    private void CancelExport()
    {
        if (isExporting)
        {
            DatabaseExporter.CancelExport();
            statusMessage = "Export operation cancelled.";
            isExporting = false;
            showProgressBar = false;
        }
    }

    private void UpdateProgress(float progress, string status)
    {
        exportProgress = progress;
        exportStatus = status;

        // If the progress is 1.0, the operation is complete
        if (Math.Abs(progress - 1.0f) < 0.001f)
        {
            isExporting = false;
            statusMessage = status;

            // Hide the progress bar after a delay
            EditorApplication.delayCall += () => 
            {
                showProgressBar = false;
                Repaint();
            };
        }
    }

    private void ExportAll()
    {
        statusMessage = "Starting export of all data...";
        isExporting = true;
        showProgressBar = true;
        exportProgress = 0f;
        exportStatus = "Initializing...";
        Repaint();

        try
        {
            DatabaseExporter.ExportAllToDBAsync(UpdateProgress);
        }
        catch (Exception ex)
        {
            isExporting = false;
            showProgressBar = false;
            statusMessage = $"Error starting export: {ex.Message}";
            Debug.LogError($"Error starting export: {ex}");
        }
    }

    private void ExportCharacters()
    {
        statusMessage = "Starting export of characters...";
        isExporting = true;
        showProgressBar = true;
        exportProgress = 0f;
        exportStatus = "Initializing...";
        Repaint();

        try
        {
            DatabaseExporter.ExportCharactersToDBAsync(UpdateProgress);
        }
        catch (Exception ex)
        {
            isExporting = false;
            showProgressBar = false;
            statusMessage = $"Error starting export: {ex.Message}";
            Debug.LogError($"Error starting export: {ex}");
        }
    }

    private void ExportItems()
    {
        statusMessage = "Starting export of items...";
        isExporting = true;
        showProgressBar = true;
        exportProgress = 0f;
        exportStatus = "Initializing...";
        Repaint();

        try
        {
            DatabaseExporter.ExportItemsToDBAsync(UpdateProgress);
        }
        catch (Exception ex)
        {
            isExporting = false;
            showProgressBar = false;
            statusMessage = $"Error starting export: {ex.Message}";
            Debug.LogError($"Error starting export: {ex}");
        }
    }
}

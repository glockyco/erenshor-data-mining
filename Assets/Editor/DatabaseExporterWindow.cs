using UnityEngine;
using UnityEditor;
using System.IO;

public class DatabaseExporterWindow : EditorWindow
{
    private Vector2 scrollPosition;
    private string statusMessage = "";
    private bool showExportOptions = true;
    private bool showExportPath = true;
    private string dbPath;

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

        // Export options section
        showExportOptions = EditorGUILayout.Foldout(showExportOptions, "Export Options");
        if (showExportOptions)
        {
            EditorGUI.indentLevel++;

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

    private void ExportAll()
    {
        statusMessage = "Exporting all data...";
        Repaint();

        try
        {
            DatabaseExporter.ExportAllToDB();
            statusMessage = $"Successfully exported all data to {dbPath}";
        }
        catch (System.Exception ex)
        {
            statusMessage = $"Error exporting data: {ex.Message}";
            Debug.LogError($"Error exporting data: {ex}");
        }
    }

    private void ExportCharacters()
    {
        statusMessage = "Exporting characters...";
        Repaint();

        try
        {
            DatabaseExporter.ExportCharactersToDB();
            statusMessage = $"Successfully exported characters to {dbPath}";
        }
        catch (System.Exception ex)
        {
            statusMessage = $"Error exporting characters: {ex.Message}";
            Debug.LogError($"Error exporting characters: {ex}");
        }
    }

    private void ExportItems()
    {
        statusMessage = "Exporting items...";
        Repaint();

        try
        {
            DatabaseExporter.ExportItemsToDB();
            statusMessage = $"Successfully exported items to {dbPath}";
        }
        catch (System.Exception ex)
        {
            statusMessage = $"Error exporting items: {ex.Message}";
            Debug.LogError($"Error exporting items: {ex}");
        }
    }
}

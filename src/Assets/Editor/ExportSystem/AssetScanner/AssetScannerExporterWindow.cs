using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public class AssetScannerExporterWindow : EditorWindow
{
    private string _outputPath;
    private SQLiteConnection _db;

    private bool _isScanning;
    private bool _cancelRequested;
    private string _status = "Idle";
    private double _elapsedSeconds;
    private Stopwatch _stopwatch;
    private AssetScanProgress _progress = new();
    private AssetScanner _activeScanner;

    private readonly HashSet<string> _selectedListenerKeys = new(StringComparer.OrdinalIgnoreCase);

    [MenuItem("Tools/Export Game Data")]
    public static void ShowWindow()
    {
        var window = GetWindow<AssetScannerExporterWindow>("Asset Scanner Exporter");
        window.minSize = new Vector2(500, 300);
        window.Show();
    }

    private bool _selectAllSteps = true;

    private void OnEnable()
    {
        _outputPath = Repository.GetDefaultDatabasePath();
        SetAllStepToggles(true);
    }

    private void OnDisable()
    {
        _cancelRequested = true;
    }

    private void OnGUI()
    {
        GUILayout.Label("Asset Scanner Exporter", EditorStyles.boldLabel);
        EditorGUILayout.Space();
        DrawConfigurationSection();
        DrawProgressSection();
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider);
        DrawStepSelectionSection();
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider);
        DrawStatusAndActionsSection();
    }

    private void DrawConfigurationSection()
    {
        GUILayout.Label("Output Database File", EditorStyles.boldLabel);
        EditorGUILayout.BeginHorizontal();
        string displayPath = _outputPath;
        string projectPath = Path.GetFullPath(Application.dataPath + "/../");
        if (!string.IsNullOrEmpty(_outputPath) && _outputPath.StartsWith(projectPath))
            displayPath = Path.GetRelativePath(projectPath, _outputPath);
        string newPath = EditorGUILayout.TextField(displayPath, GUILayout.ExpandWidth(true));
        if (newPath != displayPath)
        {
            try
            {
                string potentialFullPath = Path.IsPathRooted(newPath)
                    ? Path.GetFullPath(newPath)
                    : Path.GetFullPath(Path.Combine(projectPath, newPath));
                string directory = Path.GetDirectoryName(potentialFullPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    _outputPath = potentialFullPath;
                    EditorPrefs.SetString(Repository.EditorPrefsKey, _outputPath);
                }
            }
            catch (System.Exception ex)
            {
                UnityEngine.Debug.LogError(
                    $"[AssetScannerExporterWindow] Invalid output path: {newPath}. Error: {ex.Message}"
                );
                EditorUtility.DisplayDialog(
                    "Invalid Path",
                    $"The specified output path is invalid:\n\n{newPath}\n\nError: {ex.Message}",
                    "OK"
                );
            }
        }
        if (GUILayout.Button("Browse...", GUILayout.Width(80)))
        {
            string directory = string.IsNullOrEmpty(_outputPath)
                ? Application.dataPath + "/.."
                : Path.GetDirectoryName(_outputPath);
            string filename = string.IsNullOrEmpty(_outputPath)
                ? Repository.DefaultFilename
                : Path.GetFileName(_outputPath);
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                directory = Application.dataPath + "/..";
            string chosenPath = EditorUtility.SaveFilePanel(
                "Select Database Output Path",
                directory,
                filename,
                "sqlite"
            );
            if (!string.IsNullOrEmpty(chosenPath))
            {
                _outputPath = chosenPath;
                EditorPrefs.SetString(Repository.EditorPrefsKey, _outputPath);
            }
        }
        EditorGUILayout.EndHorizontal();
    }

    private void DrawProgressSection()
    {
        if (!_isScanning)
            return;
        float progress = (_progress.Total > 0) ? (float)_progress.Current / _progress.Total : 0f;
        string label = $"{_progress.Phase ?? ""} ({_progress.Current}/{_progress.Total})";
        GUILayout.Space(10);
        EditorGUILayout.LabelField("Progress:", EditorStyles.boldLabel);
        Rect rect = GUILayoutUtility.GetRect(18, 18, "TextField");
        EditorGUI.ProgressBar(rect, progress, label);
        string timeStr =
            _elapsedSeconds > 0
                ? TimeSpan.FromSeconds(_elapsedSeconds).ToString(@"hh\:mm\:ss")
                : "00:00:00";
        EditorGUILayout.LabelField($"Elapsed: {timeStr}", EditorStyles.miniLabel);
    }

    private void DrawStepSelectionSection()
    {
        GUILayout.Label("Export Steps", EditorStyles.boldLabel);
        EditorGUI.BeginChangeCheck();
        _selectAllSteps = EditorGUILayout.ToggleLeft(" Select / Deselect All", _selectAllSteps);
        if (EditorGUI.EndChangeCheck())
        {
            SetAllStepToggles(_selectAllSteps);
        }

        EditorGUI.BeginDisabledGroup(_selectAllSteps);
        foreach (ExportListenerDefinition definition in ExportListenerRegistry.Definitions)
        {
            bool selected = _selectedListenerKeys.Contains(definition.Key);
            bool updated = EditorGUILayout.ToggleLeft(definition.Label, selected);
            if (updated != selected)
            {
                if (updated)
                    _selectedListenerKeys.Add(definition.Key);
                else
                    _selectedListenerKeys.Remove(definition.Key);
            }
        }
        EditorGUI.EndDisabledGroup();
    }

    private void SetAllStepToggles(bool value)
    {
        _selectedListenerKeys.Clear();
        if (value)
        {
            foreach (ExportListenerDefinition definition in ExportListenerRegistry.Definitions)
                _selectedListenerKeys.Add(definition.Key);
        }
    }

    private void StartScanAndExport()
    {
        _status = "Running";
        _elapsedSeconds = 0;
        _isScanning = true;
        _cancelRequested = false;
        _progress = new AssetScanProgress();

        _activeScanner = new AssetScanner();

        _db = new SQLiteConnection(_outputPath);

        ExportListenerRegistry.Register(_activeScanner, _db, _selectedListenerKeys);

        _stopwatch = Stopwatch.StartNew();
        EditorCoroutineRunner.StartCoroutine(ScanAndExportCoroutine());
    }

    private IEnumerator ScanAndExportCoroutine()
    {
        var scanCoroutine = _activeScanner.ScanAllAssetsCoroutine(
            () => _cancelRequested,
            progress =>
            {
                _progress = progress;
                Repaint();
            }
        );
        while (scanCoroutine.MoveNext())
        {
            _elapsedSeconds = _stopwatch.Elapsed.TotalSeconds;
            Repaint();
            yield return scanCoroutine.Current;
        }
        _elapsedSeconds = _stopwatch.Elapsed.TotalSeconds;
        _isScanning = false;
        _status = _cancelRequested ? "Cancelled" : "Done";
        Repaint();
    }

    private void DrawStatusAndActionsSection()
    {
        GUILayout.Label("Overall Status:", EditorStyles.boldLabel);
        EditorGUILayout.LabelField(_status);
        EditorGUILayout.Space();
        EditorGUILayout.BeginHorizontal();
        bool anyStepSelected = _selectedListenerKeys.Count > 0;
        EditorGUI.BeginDisabledGroup(
            _isScanning || !anyStepSelected || string.IsNullOrEmpty(_outputPath)
        );
        if (GUILayout.Button("Export Selected Steps", GUILayout.Height(30)))
        {
            StartScanAndExport();
        }
        EditorGUI.EndDisabledGroup();
        EditorGUI.BeginDisabledGroup(!_isScanning);
        if (GUILayout.Button("Cancel Export", GUILayout.Height(30)))
        {
            _cancelRequested = true;
        }
        EditorGUI.EndDisabledGroup();
        EditorGUILayout.EndHorizontal();
        EditorGUILayout.Space();
        bool fileExists =
            !_isScanning && !string.IsNullOrEmpty(_outputPath) && File.Exists(_outputPath);
        EditorGUI.BeginDisabledGroup(!fileExists);
        if (GUILayout.Button("Open Output Folder"))
        {
            EditorUtility.RevealInFinder(_outputPath);
        }
        EditorGUI.EndDisabledGroup();
    }
}

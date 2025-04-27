using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using UnityEditor;
using UnityEngine;

public class DatabaseExporterWindow : EditorWindow
{
    // --- Constants ---
    private const string EDITOR_PREFS_KEY_DB_PATH = "Erenshor_DatabaseExporter_OutputPath";
    private const string DEFAULT_DB_FILENAME = "Erenshor.sqlite";

    // --- Internal State ---
    private class StepStatus
    {
        public string Name { get; set; }
        public IExportStep StepInstance { get; set; } // Keep instance for easy access
        public bool IsSelected { get; set; } = true; // Default to selected
        public string StatusText { get; set; } = "Pending"; // Pending, Running, Done, Failed, Cancelled, Skipped
        public int CurrentProgress { get; set; } = 0;
        public int TotalProgress { get; set; } = 0;
        public string ErrorMessage { get; set; } = null; // Store error message on failure

        public bool IsRunning => StatusText == "Running";
        public bool IsFinished => StatusText == "Done" || StatusText == "Failed" || StatusText == "Cancelled" || StatusText == "Skipped";

        public string DisplayText => IsRunning && TotalProgress > 0
            ? $"Running ({CurrentProgress}/{TotalProgress})"
            : StatusText;

        public GUIContent IconContent
        {
            get
            {
                switch (StatusText)
                {
                    case "Running":
                        return EditorGUIUtility.IconContent("d_PlayButton");
                    case "Done":
                        return EditorGUIUtility.IconContent("d_FilterSelectedOnly");
                    case "Failed":
                        return EditorGUIUtility.IconContent("d_console.erroricon.sml");
                    case "Cancelled":
                        return EditorGUIUtility.IconContent("d_PauseButton");
                    case "Skipped":
                        return EditorGUIUtility.IconContent("d_StepButton");
                    case "Pending":
                    default:
                        return GUIContent.none;
                }
            }
        }

        public GUIContent LabelContent => new GUIContent($" {Name}", ErrorMessage); // Add space for icon, use tooltip for error
    }

    private Exporter _exporter;
    private string _overallStatus = "Ready";
    private List<StepStatus> _stepStatuses = new List<StepStatus>();
    private Vector2 _scrollPosition;
    private CancellationTokenSource _cancellationTokenSource;
    private bool _isExportRunning = false;
    private string _outputPath = ""; // Holds the full path to the output DB
    private bool _selectAllSteps = true; // For the "Select/Deselect All" checkbox

    // Dependencies needed by steps (consider a better DI approach later if needed)
    private readonly LootTableProbabilityCalculator _probabilityCalculator = new LootTableProbabilityCalculator();

    // --- Menu Item & Window Setup ---
    [MenuItem("Tools/Database/Export Database")]
    public static void ShowWindow()
    {
        var window = GetWindow<DatabaseExporterWindow>("Database Exporter");
        window.minSize = new Vector2(500, 500); // Increased size slightly
        window.Show();
    }

    // --- Unity Lifecycle Methods ---
    private void OnEnable()
    {
        if (_exporter == null) _exporter = new Exporter();

        // Load saved path or set default
        _outputPath = EditorPrefs.GetString(EDITOR_PREFS_KEY_DB_PATH, GetDefaultDatabasePath());

        // Initialize step statuses if list is empty or doesn't match known steps
        InitializeStepStatusesIfNeeded();
    }

    private void OnDisable()
    {
        RequestCancellation();
    }

    private void OnDestroy()
    {
        RequestCancellation();
        _cancellationTokenSource?.Dispose();
    }

    // --- UI Drawing (OnGUI) ---
    private void OnGUI()
    {
        if (_exporter == null) _exporter = new Exporter(); // Safety check

        InitializeStepStatusesIfNeeded(); // Ensure list is populated and up-to-date before drawing

        GUILayout.Label("Database Exporter", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // --- Configuration Section ---
        DrawConfigurationSection();
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider); // Separator

        // --- Step Selection Section ---
        DrawStepSelectionSection();
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider); // Separator

        // --- Status & Actions Section ---
        DrawStatusAndActionsSection();
    }

    // --- UI Drawing Helpers ---

    private void DrawConfigurationSection()
    {
        GUILayout.Label("Output Database File", EditorStyles.boldLabel);
        EditorGUILayout.BeginHorizontal();
        // Display path relative to project if possible for better readability
        string displayPath = _outputPath;
        string projectPath = Path.GetFullPath(Application.dataPath + "/../");
        if (_outputPath.StartsWith(projectPath))
        {
            displayPath = Path.GetRelativePath(projectPath, _outputPath);
        }

        string newPath = EditorGUILayout.TextField(displayPath, GUILayout.ExpandWidth(true));
        // If user manually edits, convert back to full path if it was relative
        if (newPath != displayPath)
        {
             try {
                 // Assume manual edit might be relative to project root
                 string potentialFullPath = Path.GetFullPath(Path.Combine(projectPath, newPath));
                 if (File.Exists(potentialFullPath) || Directory.Exists(Path.GetDirectoryName(potentialFullPath)))
                 {
                     _outputPath = potentialFullPath;
                 } else {
                     // If it doesn't seem valid relative to project, treat as absolute
                     _outputPath = Path.GetFullPath(newPath);
                 }
                 SaveOutputPath(); // Save changes
             } catch (Exception ex) {
                 Debug.LogWarning($"Could not resolve manually entered path '{newPath}': {ex.Message}");
                 // Keep old path on error
             }
        }


        if (GUILayout.Button("Browse...", GUILayout.Width(80)))
        {
            string directory = string.IsNullOrEmpty(_outputPath) ? Application.dataPath + "/.." : Path.GetDirectoryName(_outputPath);
            string filename = string.IsNullOrEmpty(_outputPath) ? DEFAULT_DB_FILENAME : Path.GetFileName(_outputPath);
            string chosenPath = EditorUtility.SaveFilePanel("Select Database Output Path", directory, filename, "sqlite");
            if (!string.IsNullOrEmpty(chosenPath))
            {
                _outputPath = chosenPath;
                SaveOutputPath(); // Save changes
            }
        }
        EditorGUILayout.EndHorizontal();
    }

    private void DrawStepSelectionSection()
    {
        GUILayout.Label("Export Steps", EditorStyles.boldLabel);

        // Select/Deselect All Checkbox
        EditorGUI.BeginChangeCheck();
        _selectAllSteps = EditorGUILayout.ToggleLeft(" Select / Deselect All", _selectAllSteps);
        if (EditorGUI.EndChangeCheck())
        {
            foreach (var status in _stepStatuses)
            {
                // Don't allow deselecting the Initialization pseudo-step
                if (status.Name != "Database Initialization")
                {
                    status.IsSelected = _selectAllSteps;
                }
            }
        }
        EditorGUILayout.Space(2);

        // Scrollable list of steps
        _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition, GUILayout.ExpandHeight(true));
        EditorGUILayout.BeginVertical(EditorStyles.helpBox);

        // Note: InitializeStepStatusesIfNeeded() was moved to the top of OnGUI

        foreach (var stepStatus in _stepStatuses)
        {
            // Skip the Initialization pseudo-step for selection/display here
            if (stepStatus.Name == "Database Initialization") continue;

            EditorGUILayout.BeginHorizontal();
            // Checkbox for selection (disabled while running)
            EditorGUI.BeginDisabledGroup(_isExportRunning);
            stepStatus.IsSelected = EditorGUILayout.Toggle(stepStatus.IsSelected, GUILayout.Width(20));
            EditorGUI.EndDisabledGroup();

            // Icon and Name with Tooltip
            GUILayout.Label(stepStatus.IconContent, GUILayout.Width(20)); // Use IconContent here
            EditorGUILayout.LabelField(stepStatus.LabelContent, GUILayout.Width(180)); // Fixed width for name

            // Status text
            EditorGUILayout.LabelField(stepStatus.DisplayText); // Takes remaining space
            EditorGUILayout.EndHorizontal();
        }
        EditorGUILayout.EndVertical();
        EditorGUILayout.EndScrollView();
    }

    private void DrawStatusAndActionsSection()
    {
        GUILayout.Label("Overall Status:", EditorStyles.boldLabel);
        EditorGUILayout.LabelField(_overallStatus);
        EditorGUILayout.Space();

        // --- Action Buttons ---
        EditorGUILayout.BeginHorizontal();
        // Export Button (disabled if running or no steps selected)
        bool anyStepSelected = _stepStatuses.Any(s => s.IsSelected && s.Name != "Database Initialization");
        EditorGUI.BeginDisabledGroup(_isExportRunning || !anyStepSelected || string.IsNullOrEmpty(_outputPath));
        if (GUILayout.Button("Export Selected Steps", GUILayout.Height(30)))
        {
            StartExport();
        }
        EditorGUI.EndDisabledGroup();

        // Cancel Button (enabled only when running)
        EditorGUI.BeginDisabledGroup(!_isExportRunning);
        if (GUILayout.Button("Cancel Export", GUILayout.Height(30)))
        {
            RequestCancellation();
        }
        EditorGUI.EndDisabledGroup();
        EditorGUILayout.EndHorizontal();
        EditorGUILayout.Space();

        // --- Utility Button ---
        bool fileExists = !_isExportRunning && !string.IsNullOrEmpty(_outputPath) && File.Exists(_outputPath);
        EditorGUI.BeginDisabledGroup(!fileExists);
        if (GUILayout.Button("Open Output Folder"))
        {
            EditorUtility.RevealInFinder(_outputPath);
        }
        EditorGUI.EndDisabledGroup();
    }


    // --- Core Logic ---

    // Initializes or re-initializes the step status list if needed
    private void InitializeStepStatusesIfNeeded()
    {
         var knownSteps = GetAllPossibleExportSteps();
         // Check if list needs refresh (e.g., count mismatch, different steps)
         if (_stepStatuses.Count == 0 || _stepStatuses.Count != knownSteps.Count + 1 || !_stepStatuses.Skip(1).Select(s => s.Name).SequenceEqual(knownSteps.Select(k => k.StepName)))
         {
             InitializeStepStatuses(knownSteps);
         }
    }

    // Helper to initialize or reset step statuses based on known steps
    private void InitializeStepStatuses(List<IExportStep> steps)
    {
        _stepStatuses.Clear();
        // Add Initialization as the first pseudo-step (always selected, not user-changeable)
        _stepStatuses.Add(new StepStatus { Name = "Database Initialization", IsSelected = true, StepInstance = null });
        // Add actual steps
        _stepStatuses.AddRange(steps.Select(step => new StepStatus
        {
            Name = step.StepName,
            StepInstance = step,
            IsSelected = _selectAllSteps // Use current state of select all toggle
        }));
        Repaint(); // Update UI after initializing
    }

    // Starts the export process with the selected list of steps
    private void StartExport()
    {
        if (_isExportRunning)
        {
            Debug.LogWarning("Exporter is already running. Please wait or cancel.");
            return;
        }
        if (string.IsNullOrEmpty(_outputPath))
        {
             EditorUtility.DisplayDialog("Export Error", "Output database path is not set. Please configure the path first.", "OK");
             _overallStatus = "Error: Output path not set.";
             Repaint();
             return;
        }

        // Get selected steps
        var stepsToRun = _stepStatuses
            .Where(s => s.IsSelected && s.StepInstance != null) // Filter selected actual steps
            .Select(s => s.StepInstance)
            .ToList();

        if (stepsToRun.Count == 0)
        {
            EditorUtility.DisplayDialog("Export Info", "No export steps selected.", "OK");
            _overallStatus = "Ready (No steps selected)";
             Repaint();
            return;
        }

        // Prepare for new export
        _isExportRunning = true;
        RequestCancellation(); // Cancel previous if any
        _cancellationTokenSource?.Dispose();
        _cancellationTokenSource = new CancellationTokenSource();

        // Reset statuses for ALL steps (including non-selected ones)
        foreach (var status in _stepStatuses)
        {
            status.StatusText = status.IsSelected ? "Pending" : "Skipped"; // Mark non-selected as skipped
            status.CurrentProgress = 0;
            status.TotalProgress = 0;
            status.ErrorMessage = null;
        }
        // Explicitly set Initialization status
        var initStatus = _stepStatuses.First(s => s.Name == "Database Initialization");
        initStatus.StatusText = "Pending";
        initStatus.ErrorMessage = null;


        _overallStatus = "Initializing...";
        Repaint(); // Update UI immediately

        // --- Define Callbacks ---
        Action<string> handleStepStart = (stepName) => {
            var status = _stepStatuses.FirstOrDefault(s => s.Name == stepName);
            if (status != null)
            {
                status.StatusText = "Running";
                status.CurrentProgress = 0;
                status.TotalProgress = 0;
                status.ErrorMessage = null;
                _overallStatus = $"Running: {stepName}";
                Repaint();
            }
        };

        Action<string, int, int> handleStepProgress = (stepName, current, total) => {
             var status = _stepStatuses.FirstOrDefault(s => s.Name == stepName);
             if (status != null && status.IsRunning)
             {
                 status.CurrentProgress = current;
                 status.TotalProgress = total;
                 Repaint();
             }
        };

        Action<string> handleStepComplete = (stepName) => {
            var status = _stepStatuses.FirstOrDefault(s => s.Name == stepName);
            if (status != null)
            {
                status.StatusText = "Done";
                Repaint();
            }
        };

        Action<string, Exception> handleStepFail = (stepName, ex) => {
            var status = _stepStatuses.FirstOrDefault(s => s.Name == stepName);
            if (status != null)
            {
                status.StatusText = "Failed!";
                status.ErrorMessage = ex.Message; // Store error message
                _overallStatus = $"Failed on step: {stepName}";
                // Log full error to console
                Debug.LogError($"Export step '{stepName}' failed: {ex.Message}\n{ex.StackTrace}");
                Repaint();
            }
        };

        Action<string> handleExportFinish = (finalStatus) => {
            _overallStatus = finalStatus;
            _isExportRunning = false; // Re-enable UI

            // Mark any steps still "Running" as "Cancelled" or "Skipped" based on final status
            bool wasCancelled = finalStatus == "Export Cancelled.";
            bool wasFailed = finalStatus.StartsWith("Export Failed");

            foreach(var status in _stepStatuses)
            {
                if (status.IsRunning) // A step was interrupted mid-run
                {
                    status.StatusText = wasCancelled ? "Cancelled" : "Failed!"; // Mark as cancelled or failed
                    if (wasFailed && string.IsNullOrEmpty(status.ErrorMessage)) status.ErrorMessage = "Export aborted due to failure in another step.";
                }
                else if (status.StatusText == "Pending" && (wasCancelled || wasFailed)) // A step never started
                {
                     status.StatusText = "Skipped";
                }
            }

            Repaint();
        };

        // Ensure exporter instance exists
        if (_exporter == null) _exporter = new Exporter();

        // Start the export process, passing the output path
        _exporter.StartExportAsync(_outputPath, stepsToRun, handleStepStart, handleStepProgress, handleStepComplete, handleStepFail, handleExportFinish, _cancellationTokenSource);
    }

    // Defines the list of all possible steps for UI initialization
    private List<IExportStep> GetAllPossibleExportSteps()
    {
        // Create instances of all steps in the desired display order
        return new List<IExportStep>
        {
            new CharacterExportStep(),
            new ItemExportStep(),
            new LootDropExportStep(_probabilityCalculator),
            new SpawnPointExportStep(),
            new SpellExportStep(),
            new SkillExportStep(),
            new AscensionExportStep(),
            new ZoneAtlasEntryExportStep(),
            new ClassExportStep(),
            new QuestExportStep(),
            new FactionExportStep(),
            new NPCDialogExportStep(),
            // Add new steps here
        };
    }

    // Helper to request cancellation
    private void RequestCancellation()
    {
        if (_isExportRunning && _cancellationTokenSource != null && !_cancellationTokenSource.IsCancellationRequested)
        {
            _cancellationTokenSource.Cancel();
            _overallStatus = "Cancellation requested...";
            Repaint();
        }
    }

    // --- Path Helpers ---
    private string GetDefaultDatabasePath()
    {
        // Default path relative to the project root (one level up from Assets)
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", DEFAULT_DB_FILENAME));
    }

    private void SaveOutputPath()
    {
        EditorPrefs.SetString(EDITOR_PREFS_KEY_DB_PATH, _outputPath);
    }
}

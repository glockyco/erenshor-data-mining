using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using SQLite;
using UnityEditor;
using UnityEngine;

// Central orchestrator
public class MasterExporter : IProgressReporter // Implements reporter to capture step progress
{
    public const string DB_PATH = "../Erenshor.sqlite"; // Central DB Path

    private List<IExportStep> _stepsToRun;
    private Action<float, string> _overallProgressCallback; // Reports overall progress to UI
    private CancellationTokenSource _cancellationTokenSource;

    private int _currentStepIndex = -1;
    private float _totalWeight = 0f;
    private float _completedWeight = 0f;
    private float _currentStepProgress = 0f; // Progress of the currently running step (0-1)
    private string _currentStatusMessage = ""; // Latest status message

    private SQLiteConnection _db;
    private Task _exportExecutionTask; // The main async task

    public bool IsRunning => _exportExecutionTask != null && !_exportExecutionTask.IsCompleted;

    // --- IProgressReporter Implementation ---
    // Called by the currently executing IExportStep
    void IProgressReporter.Report(float progress, string message)
    {
        // Store the latest progress and message from the step
        _currentStepProgress = Mathf.Clamp01(progress);
        _currentStatusMessage = message;
        // The UI update loop will read these values
    }
    // --- End IProgressReporter ---

    public void StartExportAsync(List<IExportStep> steps, Action<float, string> progressCallback)
    {
        if (IsRunning)
        {
            Debug.LogWarning("Exporter is already running.");
            return;
        }

        // --- Initialization ---
        _stepsToRun = steps ?? throw new ArgumentNullException(nameof(steps));
        _overallProgressCallback = progressCallback ?? ((_, __) => { });
        _cancellationTokenSource = new CancellationTokenSource();

        _currentStepIndex = -1;
        _completedWeight = 0f;
        _totalWeight = _stepsToRun.Sum(step => Mathf.Max(0.1f, step.ProgressWeight)); // Ensure non-zero weight
        _currentStepProgress = 0f;
        _currentStatusMessage = "Initializing...";
        _db = null;

        // --- Start Async Execution ---
        _exportExecutionTask = RunExportLifecycleAsync(_cancellationTokenSource.Token);

        // --- Start UI Update Loop ---
        // Use EditorApplication.update to periodically check task status and report progress
        EditorApplication.update -= MonitorProgress; // Ensure no duplicates if run multiple times
        EditorApplication.update += MonitorProgress;
        _overallProgressCallback(0f, _currentStatusMessage); // Initial status
    }

    // Main async method controlling the export lifecycle
    private async Task RunExportLifecycleAsync(CancellationToken cancellationToken)
    {
        try
        {
            // 1. Initialize Database (Synchronous part)
            ReportProgressInternal(0f, "Initializing Database...");
            InitializeDatabase(); // Creates connection and tables
            if (_db == null) throw new InvalidOperationException("Database initialization failed.");
            ReportProgressInternal(0f, "Database Initialized.");
            await Task.Yield(); // Allow UI update

            // 2. Execute Steps Sequentially
            for (int i = 0; i < _stepsToRun.Count; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                _currentStepIndex = i;
                IExportStep currentStep = _stepsToRun[i];

                // Reset progress for the new step and report start
                ReportProgressInternal(0f, $"Starting Step: {currentStep.StepName}...");
                await Task.Yield(); // Allow UI update

                // --- Execute the step ---
                // The step itself calls IProgressReporter.Report, updating _currentStepProgress and _currentStatusMessage
                await currentStep.ExecuteAsync(_db, this, cancellationToken);

                // --- Mark step as complete ---
                // Ensure step progress is 1.0 after execution finishes successfully
                ReportProgressInternal(1.0f, $"Finished Step: {currentStep.StepName}.");
                _completedWeight += Mathf.Max(0.1f, currentStep.ProgressWeight); // Add weight after completion
                await Task.Yield(); // Allow UI update
            }

            // 3. Final Completion State
            ReportProgressInternal(1.0f, "Export Completed Successfully.");
        }
        catch (OperationCanceledException)
        {
            ReportProgressInternal(_currentStepProgress, "Export Cancelled."); // Report cancellation
        }
        catch (Exception ex)
        {
            Debug.LogError($"Export failed during step '{(_currentStepIndex >= 0 && _currentStepIndex < _stepsToRun.Count ? _stepsToRun[_currentStepIndex].StepName : "Initialization")}': {ex.Message}\n{ex.StackTrace}");
            ReportProgressInternal(_currentStepProgress, $"Export Failed: {ex.Message}"); // Report failure
        }
        finally
        {
            // Cleanup resources regardless of outcome
            _db?.Close(); // Use Close instead of Dispose for SQLite-net standard practice
            _db?.Dispose(); // Still call Dispose for good measure
            _db = null;
            // The MonitorProgress loop will handle unregistering itself when the task completes.
        }
    }

    // Internal method to update state, called by the runner itself
    private void ReportProgressInternal(float stepProgress, string message)
    {
        _currentStepProgress = Mathf.Clamp01(stepProgress);
        _currentStatusMessage = message;
    }

    // Called by EditorApplication.update to refresh the UI
    private void MonitorProgress()
    {
        if (_exportExecutionTask == null) // Should not happen if started correctly
        {
            EditorApplication.update -= MonitorProgress;
            return;
        }

        // Calculate overall progress based on current state
        float overallProgress = CalculateOverallProgress();

        // Report to the UI callback
        _overallProgressCallback(overallProgress, _currentStatusMessage);

        // Check if the task has finished (completed, faulted, or cancelled)
        if (_exportExecutionTask.IsCompleted)
        {
            EditorApplication.update -= MonitorProgress; // Stop monitoring
            // Final cleanup of CancellationTokenSource
            _cancellationTokenSource?.Dispose();
            _cancellationTokenSource = null;
            // Ensure the window repaints with the final status
            // Use delayCall to avoid issues calling GetWindow during OnGUI repaint
            EditorApplication.delayCall += () => {
                 var window = EditorWindow.GetWindow<DatabaseExporterWindow>(false); // Don't focus
                 if (window != null) window.Repaint();
            };
        }
    }

    // Synchronous DB Initialization part
    private void InitializeDatabase()
    {
        string dbPath = "";
        try
        {
            dbPath = Path.GetFullPath(Path.Combine(Application.dataPath, DB_PATH));
            // Ensure directory exists
            Directory.CreateDirectory(Path.GetDirectoryName(dbPath));
            _db = new SQLiteConnection(dbPath);

            // Collect all unique record types needed by *all* steps
            var allRecordTypes = _stepsToRun
                .SelectMany(step => step.GetRequiredRecordTypes() ?? Enumerable.Empty<Type>())
                .Where(t => t != null && t.IsClass) // Ensure it's a valid type
                .Distinct()
                .ToList();

            // Create/Clear tables within a single transaction
            _db.RunInTransaction(() => {
                foreach (var type in allRecordTypes)
                {
                    // Check if type has a parameterless constructor needed by SQLite-net
                    if (type.GetConstructor(Type.EmptyTypes) == null)
                    {
                         Debug.LogWarning($"Skipping table creation for type '{type.Name}' because it lacks a parameterless constructor.");
                         continue;
                    }

                    _db.CreateTable(type);
                    // Use reflection to call DeleteAll<T>
                    var deleteMethod = typeof(SQLiteConnection).GetMethod("DeleteAll", Type.EmptyTypes)?.MakeGenericMethod(type);
                    if (deleteMethod != null)
                    {
                        deleteMethod.Invoke(_db, null);
                    } else {
                         Debug.LogWarning($"Could not find DeleteAll method for type {type.Name}");
                    }
                }
            });
             Debug.Log($"Database initialized at {dbPath}. Tables created/cleared for: {string.Join(", ", allRecordTypes.Select(t=>t.Name))}");
        }
        catch (Exception ex)
        {
            Debug.LogError($"Failed to initialize database at {dbPath}: {ex.Message}\n{ex.StackTrace}");
            _db?.Close();
            _db?.Dispose();
            _db = null;
            throw; // Re-throw to be caught by RunExportLifecycleAsync
        }
    }

    public void CancelExport()
    {
        if (IsRunning && _cancellationTokenSource != null && !_cancellationTokenSource.IsCancellationRequested)
        {
            _cancellationTokenSource.Cancel();
            // The RunExportLifecycleAsync task will catch the OperationCanceledException.
            // Update status immediately for feedback.
            ReportProgressInternal(_currentStepProgress, "Cancellation requested...");
            // Trigger UI update manually if needed, though MonitorProgress should pick it up
             _overallProgressCallback(CalculateOverallProgress(), _currentStatusMessage);
        }
    }

     // Helper to calculate overall progress based on current state (used for cancellation feedback and MonitorProgress)
    private float CalculateOverallProgress()
    {
        if (_totalWeight <= 0) return 0f;
        float currentStepContribution = 0f;
        if (_currentStepIndex >= 0 && _currentStepIndex < _stepsToRun.Count)
        {
            // Use the weight of the current step and its reported progress
            currentStepContribution = Mathf.Max(0.1f, _stepsToRun[_currentStepIndex].ProgressWeight) * _currentStepProgress;
        }
        return Mathf.Clamp01((_completedWeight + currentStepContribution) / _totalWeight);
    }
}

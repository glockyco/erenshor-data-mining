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

// Central orchestrator for the export process
public class Exporter
{
    // --- Public Status Constants ---
    public const string STATUS_SUCCESS = "Export Completed Successfully.";
    public const string STATUS_CANCELLED = "Export Cancelled.";
    public const string STATUS_FAILED_PREFIX = "Export Failed on step: "; // Used for constructing failure messages

    // --- Internal State ---
    private SQLiteConnection _db;
    private CancellationTokenSource _cancellationTokenSource;
    private Task _exportExecutionTask;

    public bool IsRunning => _exportExecutionTask != null && !_exportExecutionTask.IsCompleted;

    // Callbacks for UI updates
    private Action<string> _onStepStart;
    private Action<string, int, int> _onStepProgress;
    private Action<string> _onStepComplete;
    private Action<string, Exception> _onStepFail;
    private Action<string> _onExportFinish; // Reports final status string

    public void StartExportAsync(
        string outputPath, // Added output path parameter
        List<IExportStep> steps,
        Action<string> onStepStart,
        Action<string, int, int> onStepProgress,
        Action<string> onStepComplete,
        Action<string, Exception> onStepFail,
        Action<string> onExportFinish,
        CancellationTokenSource cancellationTokenSource)
    {
        if (IsRunning)
        {
            Debug.LogWarning("Exporter is already running.");
            return;
        }
        if (string.IsNullOrEmpty(outputPath))
        {
             Debug.LogError("Output path cannot be empty.");
             onExportFinish?.Invoke($"{STATUS_FAILED_PREFIX}Initialization (Output path not set)"); // Report failure immediately using prefix
             return;
        }

        // --- Initialization ---
        _onStepStart = onStepStart ?? ((_) => { });
        _onStepProgress = onStepProgress ?? ((_, __, ___) => { });
        _onStepComplete = onStepComplete ?? ((_) => { });
        _onStepFail = onStepFail ?? ((_, __) => { });
        _onExportFinish = onExportFinish ?? ((_) => { });
        _cancellationTokenSource = cancellationTokenSource ?? throw new ArgumentNullException(nameof(cancellationTokenSource));
        _db = null;

        // --- Start Async Execution ---
        // Pass outputPath to the lifecycle method
        _exportExecutionTask = RunExportLifecycleAsync(outputPath, steps, _cancellationTokenSource.Token);

        // No EditorApplication.update loop needed anymore
    }

    // Main async method controlling the export lifecycle
    private async Task RunExportLifecycleAsync(string outputPath, List<IExportStep> stepsToRun, CancellationToken cancellationToken)
    {
        string finalStatus = "Unknown"; // Default status
        string currentStepName = "Initialization";

        try
        {
            // 1. Initialize Database (Synchronous part, but run async)
            _onStepStart("Database Initialization"); // Report init as a step visually
            // Pass outputPath to InitializeDatabase
            await Task.Run(() => InitializeDatabase(outputPath, stepsToRun), cancellationToken);
            if (_db == null) throw new InvalidOperationException("Database initialization failed.");
            _onStepComplete("Database Initialization");
            await Task.Yield(); // Allow UI update

            // 2. Execute Steps Sequentially
            for (int i = 0; i < stepsToRun.Count; i++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                IExportStep currentStep = stepsToRun[i];
                currentStepName = currentStep.StepName;

                // Report step start
                _onStepStart(currentStepName);
                await Task.Yield(); // Allow UI update

                // Create the progress callback for this specific step
                Action<int, int> stepProgressCallback = (current, total) => {
                    // Forward the progress report to the UI callback, including the step name
                    _onStepProgress(currentStepName, current, total);
                };

                // --- Execute the step ---
                await currentStep.ExecuteAsync(_db, stepProgressCallback, cancellationToken);

                // --- Mark step as complete ---
                _onStepComplete(currentStepName);
                await Task.Yield(); // Allow UI update
            }

            // 3. Final Completion State
            finalStatus = STATUS_SUCCESS; // Use constant
        }
        catch (OperationCanceledException)
        {
            finalStatus = STATUS_CANCELLED; // Use constant
            // Optionally report the current step as cancelled/failed if needed by UI logic
            // _onStepFail(currentStepName, new OperationCanceledException());
        }
        catch (Exception ex)
        {
            Debug.LogError($"Export failed during step '{currentStepName}': {ex.Message}\n{ex.StackTrace}");
            finalStatus = $"{STATUS_FAILED_PREFIX}{currentStepName}"; // Use constant prefix
            _onStepFail(currentStepName, ex); // Report the specific failure
        }
        finally
        {
            // Cleanup resources regardless of outcome
            _db?.Close();
            _db?.Dispose();
            _db = null;

            // Report final overall status using the determined finalStatus string
            _onExportFinish(finalStatus);

            // Task is complete, no need to manage CancellationTokenSource disposal here,
            // the window should dispose it when starting a new export or closing.
        }
    }

    // Synchronous DB Initialization part - now accepts outputPath
    private void InitializeDatabase(string outputPath, List<IExportStep> stepsToRun)
    {
        string dbPath = "";
        try
        {
            // Use the provided outputPath, ensuring it's a full path
            dbPath = Path.GetFullPath(outputPath);
            Directory.CreateDirectory(Path.GetDirectoryName(dbPath)); // Ensure directory exists
            _db = new SQLiteConnection(dbPath);

            // Collect all unique record types needed by *all* steps
            var allRecordTypes = stepsToRun // Use the passed steps
                .SelectMany(step => step.GetRequiredRecordTypes() ?? Enumerable.Empty<Type>())
                .Where(t => t != null && t.IsClass)
                .Distinct()
                .ToList();

            // Create/Clear tables within a single transaction
            _db.RunInTransaction(() => {
                foreach (var type in allRecordTypes)
                {
                    if (type.GetConstructor(Type.EmptyTypes) == null)
                    {
                         Debug.LogWarning($"Skipping table creation for type '{type.Name}' because it lacks a parameterless constructor.");
                         continue;
                    }

                    _db.CreateTable(type);
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

    // Cancel method remains simple
    public void CancelExport()
    {
        if (IsRunning && _cancellationTokenSource != null && !_cancellationTokenSource.IsCancellationRequested)
        {
            _cancellationTokenSource.Cancel();
            // The RunExportLifecycleAsync task will catch the OperationCanceledException.
            // The UI will be updated via the onExportFinish callback.
        }
    }
}

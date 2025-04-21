using System;
using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class DatabaseManager
{
    private readonly DatabaseOperation _operation;

    // Delegate for export operations
    public delegate void ExportOperation(SQLiteConnection db, Dictionary<string, object> state);

    public DatabaseManager()
    {
        _operation = new DatabaseOperation();
    }

    // Generic async export method
    public void ExportAsync(
        Dictionary<string, object> initialState,
        Action<Dictionary<string, object>, DatabaseOperation.ProgressCallback> updateMethod,
        DatabaseOperation.ProgressCallback progressCallback = null
    ) {
        DatabaseOperation.ResetCancelFlag();

        // Store the progress callback in the state
        initialState["progressCallback"] = progressCallback;

        // Start the asynchronous operation
        DatabaseOperation.StartAsyncOperation(() => updateMethod(initialState, progressCallback));
    }

    // Generic async update method
    public void GenericExportAsyncUpdate(
        Dictionary<string, object> state,
        DatabaseOperation.ProgressCallback progressCallback,
        Dictionary<string, ExportOperation> stageOperations,
        string completionMessage
    ) {
        // Check if the operation has been cancelled
        if (DatabaseOperation._cancelRequested)
        {
            progressCallback?.Invoke(1.0f, "Export cancelled");
            DatabaseOperation.CleanupDelegate();
            DatabaseOperation.ResetCancelFlag();
            return;
        }

        // Check if the operation has completed
        if ((bool)state["completed"])
        {
            string dbPath = (string)state["dbPath"];

            // Replace format placeholders with actual values from the dictionary
            string message = completionMessage;
            foreach (var key in state.Keys)
            {
                message = message.Replace($"{{0[{key}]}}", state[key]?.ToString() ?? "0");
            }

            progressCallback?.Invoke(1.0f, message);
            Debug.Log($"{message} to SQLite database at {dbPath}");

            DatabaseOperation.CleanupDelegate();
            return;
        }

        // Get the current stage and execute the corresponding operation
        string stage = (string)state["stage"];
        if (stageOperations.TryGetValue(stage, out ExportOperation operation))
        {
            SQLiteConnection db = state["db"] as SQLiteConnection;
            if (db == null && stage == "init")
            {
                // Initialize the database
                string dbPath = (string)state["dbPath"];
                db = new SQLiteConnection(dbPath);
                state["db"] = db;
            }

            // Execute the operation for the current stage
            operation(db, state);
        }
        else
        {
            Debug.LogError($"Unknown stage: {stage}");
            state["completed"] = true;
        }
    }

    // Initialize a database connection
    public SQLiteConnection InitializeDatabase(string dbPath)
    {
        return new SQLiteConnection(dbPath);
    }
}
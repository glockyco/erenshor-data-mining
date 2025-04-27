using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using SQLite;

// The flexible export step interface
public interface IExportStep
{
    // --- Metadata ---
    string StepName { get; }
    // ProgressWeight removed

    // --- Pre-Execution ---
    // Informs the runner which DB record types this step *might* write to.
    // Used for initializing/clearing tables before any step runs.
    IEnumerable<Type> GetRequiredRecordTypes();

    // --- Execution ---
    // Performs the entire export logic for this step.
    // - Finds/Generates data (from any source).
    // - Processes data.
    // - Interacts with the database (Insert, Update, Delete).
    // - Reports progress (current count, total count) via the reportProgress action.
    // - Respects the cancellation token.
    Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken);
}

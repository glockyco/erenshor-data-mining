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
    float ProgressWeight { get; } // Relative weight for overall progress calculation

    // --- Pre-Execution ---
    // Informs the runner which DB record types this step *might* write to.
    // Used for initializing/clearing tables before any step runs.
    IEnumerable<Type> GetRequiredRecordTypes();

    // --- Execution ---
    // Performs the entire export logic for this step.
    // - Finds/Generates data (from any source).
    // - Processes data.
    // - Interacts with the database (Insert, Update, Delete).
    // - Reports progress (0.0 to 1.0) via the reporter.
    // - Respects the cancellation token.
    Task ExecuteAsync(SQLiteConnection db, IProgressReporter reporter, CancellationToken cancellationToken);
}

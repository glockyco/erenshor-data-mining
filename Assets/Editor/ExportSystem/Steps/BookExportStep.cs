using SQLite;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

public class BookExportStep : IExportStep
{
    public string StepName => "Books";

    public IEnumerable<Type> GetRequiredRecordTypes()
    {
        return new[] { typeof(BookDBRecord) };
    }

    public async Task ExecuteAsync(SQLiteConnection db, Action<int, int> reportProgress, CancellationToken cancellationToken)
    {
        await Task.Run(() =>
        {
            var books = AllBooks.Books;

            // Calculate total pages for progress reporting
            int totalPages = books.Sum(entry => entry.Value?.Length ?? 0);
            int pagesProcessed = 0;

            if (totalPages == 0)
            {
                Debug.LogWarning("No book pages found to export.");
                reportProgress?.Invoke(0, 0);
                return; // Exit if there's nothing to process
            }

            reportProgress?.Invoke(0, totalPages);

            db.RunInTransaction(() =>
            {
                foreach (var bookEntry in books)
                {
                    cancellationToken.ThrowIfCancellationRequested();

                    var bookName = bookEntry.Key;
                    var pages = bookEntry.Value;

                    if (pages == null || pages.Length == 0)
                    {
                        Debug.LogWarning($"Book '{bookName}' has no pages. Skipping.");
                        continue; // Skip this book if it has no pages
                    }

                    for (int i = 0; i < pages.Length; i++)
                    {
                        cancellationToken.ThrowIfCancellationRequested();

                        var record = new BookDBRecord
                        {
                            BookTitle = bookName,
                            PageNumber = i, // Store the 0-based page index
                            PageContent = pages[i] ?? "" // Use page content, handle potential null
                        };

                        db.Insert(record);
                        pagesProcessed++;

                        if (pagesProcessed % 10 == 0 || pagesProcessed == totalPages)
                        {
                             // The actual UI update is handled by DatabaseExporterWindow via EditorApplication.delayCall
                             reportProgress?.Invoke(pagesProcessed, totalPages);
                        }
                    }
                }
            });

            // Ensure final progress is reported after the transaction completes
            reportProgress?.Invoke(pagesProcessed, totalPages);

        }, cancellationToken); // Pass cancellationToken to Task.Run
    }
}

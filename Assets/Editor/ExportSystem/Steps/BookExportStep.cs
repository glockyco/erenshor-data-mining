using SQLite;
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Database;

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
            var books = AllBooks.Books; // Access the data from AllBooks

            int totalBooks = books.Count;
            int currentBook = 0;

            foreach (var bookEntry in books)
            {
                cancellationToken.ThrowIfCancellationRequested();

                var bookName = bookEntry.Key;
                var pages = bookEntry.Value;

                var record = new BookDBRecord
                {
                    BookName = bookName,
                    PageContent = pages.Length > 0 ? pages[0] : "",
                };

                db.Insert(record);

                currentBook++;
                reportProgress?.Invoke(currentBook, totalBooks);
            }
        }, cancellationToken);
    }
}

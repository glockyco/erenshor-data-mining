using System.Collections.Generic;
using Database;
using UnityEngine;

public class BookExportCollector
{
    public readonly List<BookDBRecord> Records = new();

    public void Collect()
    {
        Debug.Log($"[BookExportCollector] Collecting...");
        Records.Clear();
        var books = AllBooks.Books;
        foreach (var bookEntry in books)
        {
            var bookName = bookEntry.Key;
            var pages = bookEntry.Value;
            if (pages == null || pages.Length == 0) continue;
            for (int i = 0; i < pages.Length; i++)
            {
                var record = new BookDBRecord
                {
                    BookTitle = bookName,
                    PageNumber = i,
                    PageContent = pages[i] ?? ""
                };
                Records.Add(record);
            }
        }
    }

    public void Reset() => Records.Clear();
}
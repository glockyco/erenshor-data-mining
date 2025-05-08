#nullable enable

using System.Collections.Generic;
using Database;
using UnityEngine;

public class BookCollector
{
    public readonly List<BookDBRecord> Records = new();

    public void Collect()
    {
        Debug.Log($"[{GetType().Name}] Collecting...");
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
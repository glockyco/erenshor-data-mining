#nullable enable

using System.Collections.Generic;
using SQLite;
using UnityEngine;

public class BookListener : IAssetScanListener<NullScriptableObject>
{
    private readonly SQLiteConnection _db;
    private readonly List<BookDBRecord> _records = new();

    public BookListener(SQLiteConnection db)
    {
        _db = db;
    }

    public void OnScanFinished()
    {
        _db.CreateTable<BookDBRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<BookDBRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnScanStarted()
    {
        Debug.Log($"[{GetType().Name}] Collecting all books...");
        
        var books = AllBooks.Books;
        foreach (var (bookName, pages) in books)
        {
            if (pages == null || pages.Length == 0) continue;
            for (var i = 0; i < pages.Length; i++)
            {
                var record = new BookDBRecord
                {
                    BookTitle = bookName,
                    PageNumber = i,
                    PageContent = pages[i] ?? ""
                };
                _records.Add(record);
            }
        }
    }
}
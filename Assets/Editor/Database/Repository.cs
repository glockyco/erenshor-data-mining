#nullable enable

using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public static class Repository
{
    public const string EditorPrefsKey = "Erenshor_Repository_FilePath";
    public const string DefaultFilename = "Erenshor.sqlite";
    
    public static SQLiteConnection CreateConnection()
    {
        return CreateConnection(GetDefaultDatabasePath());
    }

    public static SQLiteConnection CreateConnection(string databasePath)
    {
        return new SQLiteConnection(databasePath);
    }

    public static string GetDefaultDatabasePath()
    {
        return EditorPrefs.GetString(EditorPrefsKey, Path.Combine(Application.dataPath, DefaultFilename));
    }
}
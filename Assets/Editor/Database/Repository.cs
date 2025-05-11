#nullable enable

using System.Collections.Generic;
using System.IO;
using SQLite;
using UnityEditor;
using UnityEngine;

public static class Repository
{
    public const string EditorPrefsKey = "Erenshor_Repository_FilePath";
    public const string DefaultFilename = "Erenshor.sqlite";

    private static readonly Dictionary<string, SQLiteConnection> Connections = new();
    
    public static SQLiteConnection CreateConnection()
    {
        return CreateConnection(GetDefaultDatabasePath());
    }

    public static SQLiteConnection CreateConnection(string databasePath)
    {
        if (!Connections.ContainsKey(databasePath))
        {
            Connections[databasePath] = new SQLiteConnection(databasePath);
        }
        return Connections[databasePath];
    }

    public static string GetDefaultDatabasePath()
    {
        return EditorPrefs.GetString(EditorPrefsKey, Path.Combine(Application.dataPath, DefaultFilename));
    }
}
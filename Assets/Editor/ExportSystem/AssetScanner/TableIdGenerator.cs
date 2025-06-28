using System.Collections.Generic;

public static class TableIdGenerator
{
    private static readonly Dictionary<string, int> _nextIds = new();

    public static void Reset(string tableName)
    {
        _nextIds[tableName] = 0;
    }

    public static int NextId(string tableName)
    {
        _nextIds.TryAdd(tableName, 0);
        return _nextIds[tableName]++;
    }

    public static void ResetAll()
    {
        _nextIds.Clear();
    }
}
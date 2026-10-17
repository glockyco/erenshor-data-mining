#nullable enable

using System;
using System.Collections;
using System.Reflection;
using UnityEngine;
using Object = UnityEngine.Object;

internal static class UnknownSpawnCandidateResolver
{
    public static bool IsSerializedField(FieldInfo field) =>
        !field.IsStatic
        && !field.IsNotSerialized
        && !field.IsInitOnly
        && (field.IsPublic || field.IsDefined(typeof(SerializeField), true));

    public static void ValidateHostCharacterCache(GameObject host, object? value)
    {
        if (value is Object obj && obj == null)
            value = null;
        var character = host.GetComponent<Character>();
        if (
            character == null
            || value != null && !(value is Character reference && reference == character)
        )
            throw new InvalidOperationException(
                $"Host character cache does not reference its own Character: {host.name}"
            );
    }

    public static Character? Resolve(object? value)
    {
        if (value is Object obj && obj == null)
            return null;
        switch (value)
        {
            case GameObject gameObject:
                return gameObject.GetComponentInChildren<Character>(true);
            case Character character:
                return character;
            case IList list:
                foreach (var item in list)
                {
                    var candidate = Resolve(item);
                    if (candidate != null)
                        return candidate;
                }
                break;
        }
        return null;
    }
}

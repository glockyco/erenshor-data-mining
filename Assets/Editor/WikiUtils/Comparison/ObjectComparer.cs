using System;
using System.Collections.Generic;
using System.Reflection;

public static class ObjectComparer
{
    private const float DefaultFloatTolerance = 0.0001f;

    public static ObjectComparisonResult Compare<T>(T a, T b)
    {
        if (ReferenceEquals(a, b))
        {
            return new ObjectComparisonResult(true, Array.Empty<ObjectFieldDifference>());
        }

        if (a == null || b == null)
        {
            return new ObjectComparisonResult(false, new[]
            {
                new ObjectFieldDifference("Object", a, b)
            });
        }

        var differences = new List<ObjectFieldDifference>();
        var type = typeof(T);

        var props = type.GetProperties(BindingFlags.Public | BindingFlags.Instance);
        props = Array.FindAll(props, p => Attribute.IsDefined(p, typeof(UseForComparison)));
        
        foreach (var prop in props)
        {
            var valueA = prop.GetValue(a);
            var valueB = prop.GetValue(b);

            if (IsFloatingPointType(prop.PropertyType))
            {
                if (!AreFloatsEqual(valueA, valueB, DefaultFloatTolerance))
                {
                    differences.Add(new ObjectFieldDifference(prop.Name, valueA, valueB));
                }
            }
            else
            {
                if (!Equals(valueA, valueB))
                {
                    differences.Add(new ObjectFieldDifference(prop.Name, valueA, valueB));
                }
            }
        }

        return new ObjectComparisonResult(differences.Count == 0, differences);
    }

    private static bool IsFloatingPointType(Type type)
    {
        return type == typeof(float) || type == typeof(float?) || type == typeof(double) || type == typeof(double?);
    }

    private static bool AreFloatsEqual(object a, object b, double tolerance)
    {
        if (a == null || b == null)
        {
            return a == b;
        }

        double da = Convert.ToDouble(a);
        double db = Convert.ToDouble(b);
        return Math.Abs(da - db) < tolerance;
    }
}
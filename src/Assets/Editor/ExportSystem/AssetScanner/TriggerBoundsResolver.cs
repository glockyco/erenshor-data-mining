#nullable enable

using System;
using UnityEngine;

internal static class TriggerBoundsResolver
{
    public static Bounds ResolveHost(Component component, string context)
    {
        var host = component.gameObject;
        var colliders = host.GetComponents<Collider>();
        var foundTrigger = false;
        var union = default(Bounds);

        foreach (var collider in colliders)
        {
            if (collider == null || !collider.enabled || !collider.isTrigger)
            {
                continue;
            }

            var bounds = collider.bounds;
            if (
                !IsFinite(bounds.center)
                || !IsFinite(bounds.extents)
                || !IsFinite(bounds.min)
                || !IsFinite(bounds.max)
            )
            {
                throw Error(
                    component,
                    context,
                    $"trigger collider '{collider.name}' (instance {collider.GetInstanceID()}) has non-finite bounds"
                );
            }

            if (!foundTrigger)
            {
                union = bounds;
                foundTrigger = true;
            }
            else
            {
                union.Encapsulate(bounds);
            }
        }

        if (!foundTrigger)
        {
            throw Error(component, context, "host has no enabled trigger colliders");
        }

        if (
            !IsFinite(union.center)
            || !IsFinite(union.extents)
            || !IsFinite(union.min)
            || !IsFinite(union.max)
        )
        {
            throw Error(component, context, "unioned trigger bounds are non-finite");
        }

        return union;
    }

    private static bool IsFinite(Vector3 value)
    {
        return IsFinite(value.x) && IsFinite(value.y) && IsFinite(value.z);
    }

    private static bool IsFinite(float value)
    {
        return !float.IsNaN(value) && !float.IsInfinity(value);
    }

    private static InvalidOperationException Error(
        Component component,
        string context,
        string reason
    )
    {
        var host = component.gameObject;
        return new InvalidOperationException(
            $"[{context}] {reason} on '{host.name}' "
                + $"(scene '{host.scene.name}', component instance {component.GetInstanceID()}, "
                + $"object instance {host.GetInstanceID()})"
        );
    }
}

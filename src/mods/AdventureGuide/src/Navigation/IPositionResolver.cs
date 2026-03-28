using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Navigation;

/// <summary>
/// Resolves a graph node to zero or more world positions.
/// Empty list means the node cannot be located right now.
/// </summary>
public interface IPositionResolver
{
    List<Vector3> Resolve(Node node);
}

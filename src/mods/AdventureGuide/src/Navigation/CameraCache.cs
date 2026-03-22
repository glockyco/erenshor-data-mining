using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Cached reference to the game camera. Avoids per-frame GetComponent calls.
/// The game camera is named "MainCam" but not tagged "MainCamera", so
/// Camera.main returns null. GameData.GameCamPos holds the camera's transform.
///
/// Invalidate on scene change or when the cached reference becomes stale.
/// </summary>
public static class CameraCache
{
    private static Camera? _camera;
    private static Transform? _lastCamPos;

    /// <summary>
    /// Get the cached camera. Returns null if GameData.GameCamPos is unavailable.
    /// Re-resolves when GameCamPos changes (e.g. after scene transition).
    /// </summary>
    public static Camera? Get()
    {
        var camPos = GameData.GameCamPos;
        if (camPos == null)
        {
            _camera = null;
            _lastCamPos = null;
            return null;
        }

        // Re-resolve if the transform changed (scene load) or camera was destroyed
        if (_lastCamPos != camPos || _camera == null)
        {
            _camera = camPos.GetComponent<Camera>();
            _lastCamPos = camPos;
        }

        return _camera;
    }

    /// <summary>Clear the cache. Called on scene transition.</summary>
    public static void Invalidate()
    {
        _camera = null;
        _lastCamPos = null;
    }
}

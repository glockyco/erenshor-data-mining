using UnityEngine;

namespace MapTileCapture.Capture;

/// <summary>How the studio shows an item's model instead of a character.</summary>
internal sealed class ItemView
{
    /// <summary>
    /// Runs on the copy before its scripts go, as the item studio needs to read
    /// them, and returns the name of the object that the copy shows, which the
    /// result reports instead of the source's name.
    /// </summary>
    public Func<GameObject, string>? Prepare { get; set; }

    /// <summary>Degrees by which the camera turns around the model, such as 180 to show a cape's back, as the player sees it.</summary>
    public float Turn { get; set; }

    /// <summary>Whether the camera looks straight at the model's broad face, as for a weapon or a shield.</summary>
    public bool FaceOn { get; set; }

    /// <summary>
    /// The direction, in the model's own frame, from which players see it,
    /// such as a furnishing from the hall; the camera keeps the preset's turn
    /// and pitch around it. Without it, the camera looks at the model's front.
    /// </summary>
    public Vector3? Facing { get; set; }

    /// <summary>Whether the model is a bow, which the face-on view shows with its grip on the left.</summary>
    public bool Bow { get; set; }
}

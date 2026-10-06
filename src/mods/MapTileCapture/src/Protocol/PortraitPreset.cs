namespace MapTileCapture.Protocol;

/// <summary>
/// The camera, light, and framing of a portrait capture. A request names the
/// preset that it expects, so captures of different presets never mix in one
/// review. Change <see cref="Name"/> together with any value here.
/// </summary>
public static class PortraitPreset
{
    public const string Name = "portrait-3";

    /// <summary>Width and height of each render, in pixels.</summary>
    public const int RenderSize = 1024;

    /// <summary>
    /// The layer that only the portrait camera renders. The game names layers
    /// 0 to 14, so the last layer is free.
    /// </summary>
    public const int StudioLayer = 31;

    /// <summary>Vertical field of view of the perspective camera, in degrees.</summary>
    public const float FieldOfView = 25f;

    /// <summary>
    /// Camera direction from the subject: turned from its front toward its
    /// right and raised above it, in degrees.
    /// </summary>
    public const float CameraYaw = -25f;
    public const float CameraPitch = -12f;

    /// <summary>
    /// The frame of the second render as a factor of the subject's larger
    /// side. It leaves room for <see cref="CropMarginFraction"/> on each side.
    /// </summary>
    public const float FrameMargin = 1.16f;

    /// <summary>How often a capture may re-aim the camera to frame the subject.</summary>
    public const int MaxAims = 3;

    /// <summary>
    /// An effect joins the framing of a subject with meshes when it alone
    /// grows the frame of the meshes by at most this factor in width and in
    /// height. Measured on the captured subjects, flames, smoke, and debris on
    /// the subject grow it by at most 1.48, while scattered cubes, embers, and
    /// swirls grow it by 1.56 or more, and beams run off the frame.
    /// </summary>
    public const float EffectFramingGrowth = 1.5f;

    public const float KeyLightIntensity = 1.0f;
    public const float KeyLightPitch = 35f;
    public const float KeyLightYaw = 40f;
    public const float FillLightIntensity = 0.35f;
    public const float FillLightPitch = 10f;
    public const float FillLightYaw = -60f;
    public const float AmbientLevel = 0.45f;

    /// <summary>Seconds that looping effects run before the render.</summary>
    public const float EffectSeconds = 1.5f;

    /// <summary>Alpha above which a pixel belongs to the subject's box.</summary>
    public const byte SubjectAlpha = 32;

    /// <summary>
    /// Transparent space kept around the subject in the output, as a fraction
    /// of the subject's larger side, so that the wiki's surface frames every
    /// subject alike.
    /// </summary>
    public const float CropMarginFraction = 0.05f;
}

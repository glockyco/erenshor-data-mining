namespace AdventureGuide.Rendering;

/// <summary>
/// ImGui color packing utilities.
/// Manual ABGR uint packing is required because System.Numerics.Vector4 loses
/// type identity after ILRepack assembly merging, breaking ImGui.NET Color
/// overloads that accept Vector4.
/// </summary>
internal static class ImGuiColors
{
    /// <summary>Convert RGBA floats (0-1) to packed uint in ImGui's ABGR format.</summary>
    public static uint Rgba(float r, float g, float b, float a)
    {
        byte br = (byte)(r * 255f + 0.5f);
        byte bg = (byte)(g * 255f + 0.5f);
        byte bb = (byte)(b * 255f + 0.5f);
        byte ba = (byte)(a * 255f + 0.5f);
        return (uint)(br | (bg << 8) | (bb << 16) | (ba << 24));
    }
}

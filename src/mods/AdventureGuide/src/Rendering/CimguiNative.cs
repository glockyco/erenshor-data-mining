using System.Runtime.InteropServices;

namespace AdventureGuide.Rendering;

/// <summary>
/// Direct P/Invoke declarations for cimgui functions that take ImVec2/ImVec4
/// parameters. These bypass ImGui.NET's managed wrappers to avoid the
/// broken marshalling that occurs after ILRepack merges System.Numerics.Vectors.
///
/// ILRepack creates a duplicate System.Numerics.Vector2 type that loses
/// Mono's SIMD intrinsic status. The duplicate type has identical layout
/// but different marshalling behavior, causing P/Invoke crashes.
///
/// Our Vec2/Vec4 structs are plain sequential floats — ILRepack has no
/// reason to touch them, and Mono marshals them correctly as POD structs.
/// </summary>
public static unsafe class CimguiNative
{
    /// <summary>
    /// ImVec2-compatible struct. Sequential layout matches cimgui's
    /// <c>struct ImVec2 { float x, y; }</c>.
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct Vec2
    {
        public float X;
        public float Y;

        public Vec2(float x, float y)
        {
            X = x;
            Y = y;
        }
    }

    /// <summary>
    /// ImVec4-compatible struct. Sequential layout matches cimgui's
    /// <c>struct ImVec4 { float x, y, z, w; }</c>.
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct Vec4
    {
        public float X;
        public float Y;
        public float Z;
        public float W;

        public Vec4(float x, float y, float z, float w)
        {
            X = x;
            Y = y;
            Z = z;
            W = w;
        }
    }

    // ── Draw list access ───────────────────────────────────────────

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr igGetForegroundDrawList_Nil();

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr igGetBackgroundDrawList_Nil();

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr igGetWindowDrawList();

    // ── Primitives ─────────────────────────────────────────────────

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddLine(
        IntPtr self,
        Vec2 p1,
        Vec2 p2,
        uint col,
        float thickness
    );

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddTriangleFilled(
        IntPtr self,
        Vec2 p1,
        Vec2 p2,
        Vec2 p3,
        uint col
    );

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddTriangle(
        IntPtr self,
        Vec2 p1,
        Vec2 p2,
        Vec2 p3,
        uint col,
        float thickness
    );

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddCircleFilled(
        IntPtr self,
        Vec2 center,
        float radius,
        uint col,
        int numSegments
    );

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddCircle(
        IntPtr self,
        Vec2 center,
        float radius,
        uint col,
        int numSegments,
        float thickness
    );

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddRectFilled(
        IntPtr self,
        Vec2 pMin,
        Vec2 pMax,
        uint col,
        float rounding,
        int flags
    );

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddText_Vec2(
        IntPtr self,
        Vec2 pos,
        uint col,
        byte* textBegin,
        byte* textEnd
    );

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    public static extern void ImDrawList_AddQuadFilled(
        IntPtr self,
        Vec2 p1,
        Vec2 p2,
        Vec2 p3,
        Vec2 p4,
        uint col
    );

    // ── Text measurement ───────────────────────────────────────

    [DllImport("cimgui", CallingConvention = CallingConvention.Cdecl)]
    private static extern void igCalcTextSize(
        Vec2* pOut,
        byte* text,
        byte* textEnd,
        byte wrapWidth,
        float maxWidth
    );

    // ── Shared UTF-8 buffer ──────────────────────────────────────────
    //
    // Encoding.UTF8.GetBytes(string) allocates a new byte[] each call.
    // We reuse a static buffer for the common case (labels, short text).
    // The buffer grows as needed and is never shrunk.
    private static byte[] _utf8Buf = new byte[256];

    private static int WriteUtf8(string text)
    {
        int needed = System.Text.Encoding.UTF8.GetByteCount(text);
        if (needed > _utf8Buf.Length)
            _utf8Buf = new byte[needed * 2];
        return System.Text.Encoding.UTF8.GetBytes(text, 0, text.Length, _utf8Buf, 0);
    }

    /// <summary>Measure text size using ImGui's current font.</summary>
    public static Vec2 CalcTextSize(string text)
    {
        if (string.IsNullOrEmpty(text))
            return new Vec2(0, 0);

        int len = WriteUtf8(text);
        Vec2 result;
        fixed (byte* p = _utf8Buf)
        {
            igCalcTextSize(&result, p, p + len, 0, -1f);
        }
        return result;
    }

    // ── Text helper ────────────────────────────────────────────────

    /// <summary>
    /// Draw text on a draw list. Handles UTF-8 encoding and pinning.
    /// </summary>
    public static void AddText(IntPtr drawList, float x, float y, uint color, string text)
    {
        if (drawList == IntPtr.Zero || string.IsNullOrEmpty(text))
            return;

        int len = WriteUtf8(text);
        fixed (byte* p = _utf8Buf)
        {
            ImDrawList_AddText_Vec2(drawList, new Vec2(x, y), color, p, p + len);
        }
    }
}

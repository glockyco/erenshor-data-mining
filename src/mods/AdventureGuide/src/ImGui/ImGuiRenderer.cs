using System.Reflection;
using System.Runtime.InteropServices;
using BepInEx.Logging;
using ImGuiNET;
using UnityEngine;
using UnityEngine.Rendering;

namespace AdventureGuide.ImGui;

/// <summary>
/// Self-contained Dear ImGui rendering backend for Unity, using CommandBuffer.
/// Ported from Lunaris's ImGuiWrap approach:
///   - Extracts cimgui.dll from embedded resources and loads via LoadLibrary
///   - Renders ImGui draw data as Unity meshes via CommandBuffer
///   - Input forwarded from Unity's Input API (no WndProc hooks — CrossOver safe)
///   - Call OnGUI() from a MonoBehaviour; the Repaint event triggers rendering
/// </summary>
public sealed class ImGuiRenderer : IDisposable
{
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr LoadLibrary(string lpFileName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool FreeLibrary(IntPtr hModule);

    private readonly ManualLogSource _log;
    private IntPtr _nativeLib;
    private IntPtr _context;
    private Texture2D? _fontTexture;
    private Material? _material;
    private CommandBuffer? _commandBuffer;

    private readonly Dictionary<IntPtr, Texture> _textures = new();
    private readonly List<Mesh> _meshPool = new();
    private readonly List<Vector3> _verts = new();
    private readonly List<Vector2> _uvs = new();
    private readonly List<Color32> _colors = new();
    private readonly List<int> _indices = new();
    private readonly MaterialPropertyBlock _mpb = new();

    /// <summary>Draw callback invoked between NewFrame and EndFrame.</summary>
    public Action? OnLayout { get; set; }

    /// <summary>True when ImGui wants to capture mouse input.</summary>
    public bool WantCaptureMouse { get; private set; }

    /// <summary>True when ImGui wants to capture keyboard input.</summary>
    public bool WantCaptureKeyboard { get; private set; }

    public ImGuiRenderer(ManualLogSource log)
    {
        _log = log;
    }

    /// <summary>
    /// Extract cimgui.dll from embedded resources, load it, and initialize
    /// the ImGui context, font atlas, and rendering material.
    /// </summary>
    public bool Init()
    {
        try
        {
            // Extract cimgui.dll from embedded resources
            var asm = Assembly.GetExecutingAssembly();
            using var stream = asm.GetManifestResourceStream("AdventureGuide.cimgui.dll");
            if (stream == null)
            {
                _log.LogError("cimgui.dll not found in embedded resources");
                return false;
            }

            var dllBytes = new byte[stream.Length];
            stream.Read(dllBytes, 0, dllBytes.Length);

            // Write to BepInEx cache directory so LoadLibrary can find it.
            // Use BepInEx.Paths.CachePath — Assembly.Location is empty under
            // ScriptEngine hot reload.
            var cacheDir = Path.Combine(BepInEx.Paths.CachePath, "imgui_native");
            Directory.CreateDirectory(cacheDir);
            var dllPath = Path.Combine(cacheDir, "cimgui.dll");

            // On hot reload, the DLL is still loaded from the previous
            // instance (file locked). Skip writing if it already exists —
            // LoadLibrary on an already-loaded DLL just increments the
            // reference count and returns the existing handle.
            if (!File.Exists(dllPath))
                File.WriteAllBytes(dllPath, dllBytes);

            _nativeLib = LoadLibrary(dllPath);
            if (_nativeLib == IntPtr.Zero)
            {
                _log.LogError($"Failed to LoadLibrary: {dllPath} (error {Marshal.GetLastWin32Error()})");
                return false;
            }

            // Create ImGui context
            _context = ImGuiNET.ImGui.CreateContext();
            var io = ImGuiNET.ImGui.GetIO();
            io.BackendFlags |= ImGuiBackendFlags.RendererHasVtxOffset;

            // Disable imgui.ini persistence (we use BepInEx config)
            unsafe
            {
                io.NativePtr->IniFilename = null;
            }

            ImGuiNET.ImGui.StyleColorsDark();

            // Build font atlas
            BuildFontAtlas();

            // Scale for readability
            var style = ImGuiNET.ImGui.GetStyle();
            style.ScaleAllSizes(1.25f);

            // Create rendering material: UI/Default with alpha blending
            CreateMaterial();

            _commandBuffer = new CommandBuffer { name = "AdventureGuide_ImGui" };

            _log.LogInfo("ImGui.NET initialized successfully");
            return true;
        }
        catch (Exception ex)
        {
            _log.LogError($"ImGui init failed: {ex}");
            return false;
        }
    }

    /// <summary>
    /// Call from MonoBehaviour.OnGUI(). Handles input, runs the layout
    /// callback, and renders on the Repaint event.
    /// </summary>
    public void OnGUI()
    {
        var current = Event.current;
        if (current == null) return;

        // Only render on Repaint
        if (current.type != EventType.Repaint) return;

        // Update display size and delta time
        var io = ImGuiNET.ImGui.GetIO();
        io.DisplaySize = new System.Numerics.Vector2(Screen.width, Screen.height);
        io.DeltaTime = Time.deltaTime > 0 ? Time.deltaTime : 1f / 60f;

        // Forward input from Unity's Input API
        UpdateInput(io);

        // Frame
        ImGuiNET.ImGui.NewFrame();
        OnLayout?.Invoke();
        ImGuiNET.ImGui.EndFrame();

        // Check capture state
        WantCaptureMouse = io.WantCaptureMouse;
        WantCaptureKeyboard = io.WantCaptureKeyboard;

        // Render
        ImGuiNET.ImGui.Render();
        RenderDrawData();
    }

    /// <summary>Register a Unity texture for use as ImGui texture ID.</summary>
    public IntPtr RegisterTexture(Texture tex)
    {
        var id = tex.GetNativeTexturePtr();
        _textures[id] = tex;
        return id;
    }

    /// <summary>Unregister a previously registered texture.</summary>
    public void UnregisterTexture(IntPtr id) => _textures.Remove(id);

    public void Dispose()
    {
        if (_context != IntPtr.Zero)
        {
            ImGuiNET.ImGui.DestroyContext(_context);
            _context = IntPtr.Zero;
        }

        foreach (var mesh in _meshPool)
            UnityEngine.Object.Destroy(mesh);
        _meshPool.Clear();

        if (_fontTexture != null)
            UnityEngine.Object.Destroy(_fontTexture);
        if (_material != null)
            UnityEngine.Object.Destroy(_material);

        _commandBuffer?.Dispose();

        if (_nativeLib != IntPtr.Zero)
        {
            FreeLibrary(_nativeLib);
            _nativeLib = IntPtr.Zero;
        }
    }

    private unsafe void BuildFontAtlas()
    {
        var io = ImGuiNET.ImGui.GetIO();
        io.Fonts.AddFontDefault();
        io.Fonts.Build();

        io.Fonts.GetTexDataAsRGBA32(out byte* pixels, out int width, out int height, out int _);

        _fontTexture = new Texture2D(width, height, TextureFormat.RGBA32, false);
        var data = new byte[width * height * 4];
        Marshal.Copy((IntPtr)pixels, data, 0, data.Length);
        _fontTexture.LoadRawTextureData(data);
        _fontTexture.Apply();

        io.Fonts.SetTexID(_fontTexture.GetNativeTexturePtr());
        // Do NOT add to _textures — the font texture uses different UV
        // transform (_MainTex_ST 1,1,0,0) than user textures (1,-1,0,1).
        // It falls through to the else branch in RenderDrawData.
    }

    private void CreateMaterial()
    {
        var shader = Shader.Find("UI/Default");
        _material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        _material.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
        _material.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
        _material.SetInt("_ZWrite", 0);
        _material.SetInt("_Cull", (int)CullMode.Off);
        _material.mainTexture = _fontTexture;
    }

    private void UpdateInput(ImGuiIOPtr io)
    {
        // Mouse position (Unity Y is bottom-up, ImGui Y is top-down)
        var mousePos = Input.mousePosition;
        io.AddMousePosEvent(mousePos.x, Screen.height - mousePos.y);

        // Mouse buttons
        io.AddMouseButtonEvent(0, Input.GetMouseButton(0));
        io.AddMouseButtonEvent(1, Input.GetMouseButton(1));
        io.AddMouseButtonEvent(2, Input.GetMouseButton(2));

        // Scroll wheel
        var scroll = Input.mouseScrollDelta;
        if (scroll.y != 0f || scroll.x != 0f)
            io.AddMouseWheelEvent(scroll.x, scroll.y);

        // Keyboard modifiers
        io.AddKeyEvent(ImGuiKey.ImGuiMod_Ctrl, Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl));
        io.AddKeyEvent(ImGuiKey.ImGuiMod_Shift, Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift));
        io.AddKeyEvent(ImGuiKey.ImGuiMod_Alt, Input.GetKey(KeyCode.LeftAlt) || Input.GetKey(KeyCode.RightAlt));

        // Common navigation keys
        AddKeyMapping(io, ImGuiKey.Tab, KeyCode.Tab);
        AddKeyMapping(io, ImGuiKey.LeftArrow, KeyCode.LeftArrow);
        AddKeyMapping(io, ImGuiKey.RightArrow, KeyCode.RightArrow);
        AddKeyMapping(io, ImGuiKey.UpArrow, KeyCode.UpArrow);
        AddKeyMapping(io, ImGuiKey.DownArrow, KeyCode.DownArrow);
        AddKeyMapping(io, ImGuiKey.PageUp, KeyCode.PageUp);
        AddKeyMapping(io, ImGuiKey.PageDown, KeyCode.PageDown);
        AddKeyMapping(io, ImGuiKey.Home, KeyCode.Home);
        AddKeyMapping(io, ImGuiKey.End, KeyCode.End);
        AddKeyMapping(io, ImGuiKey.Insert, KeyCode.Insert);
        AddKeyMapping(io, ImGuiKey.Delete, KeyCode.Delete);
        AddKeyMapping(io, ImGuiKey.Backspace, KeyCode.Backspace);
        AddKeyMapping(io, ImGuiKey.Space, KeyCode.Space);
        AddKeyMapping(io, ImGuiKey.Enter, KeyCode.Return);
        AddKeyMapping(io, ImGuiKey.Escape, KeyCode.Escape);
        AddKeyMapping(io, ImGuiKey.KeypadEnter, KeyCode.KeypadEnter);
        AddKeyMapping(io, ImGuiKey.A, KeyCode.A);
        AddKeyMapping(io, ImGuiKey.C, KeyCode.C);
        AddKeyMapping(io, ImGuiKey.V, KeyCode.V);
        AddKeyMapping(io, ImGuiKey.X, KeyCode.X);

        // Text input
        foreach (char c in Input.inputString)
        {
            if (c >= ' ' && c != '\u007f')
                io.AddInputCharacter(c);
        }
    }

    private static void AddKeyMapping(ImGuiIOPtr io, ImGuiKey imguiKey, KeyCode unityKey)
    {
        io.AddKeyEvent(imguiKey, Input.GetKey(unityKey));
    }

    /// <summary>
    /// Render ImGui draw data using Unity CommandBuffer + DrawMesh.
    /// Each ImDrawList becomes a Unity Mesh; each ImDrawCmd becomes a submesh
    /// drawn with scissor rects and per-command texture overrides.
    /// </summary>
    private unsafe void RenderDrawData()
    {
        if (_commandBuffer == null || _material == null) return;

        var drawData = ImGuiNET.ImGui.GetDrawData();
        if (drawData.CmdListsCount == 0) return;

        float screenW = Screen.width;
        float screenH = Screen.height;
        var projection = Matrix4x4.Ortho(0, screenW, screenH, 0, -1, 1);

        _commandBuffer.Clear();
        _commandBuffer.SetProjectionMatrix(projection);
        _commandBuffer.SetViewMatrix(Matrix4x4.identity);

        float offsetX = drawData.DisplayPos.X;
        float offsetY = drawData.DisplayPos.Y;

        // Ensure we have enough pooled meshes
        while (_meshPool.Count < drawData.CmdListsCount)
        {
            var m = new Mesh { indexFormat = IndexFormat.UInt32 };
            m.MarkDynamic();
            _meshPool.Add(m);
        }

        for (int n = 0; n < drawData.CmdListsCount; n++)
        {
            var cmdList = drawData.CmdListsRange[n];
            var vtxBuffer = cmdList.VtxBuffer;
            var idxBuffer = cmdList.IdxBuffer;
            var cmdBuffer = cmdList.CmdBuffer;

            // Build vertex data
            _verts.Clear();
            _uvs.Clear();
            _colors.Clear();

            for (int v = 0; v < vtxBuffer.Size; v++)
            {
                var vtx = vtxBuffer[v];
                _verts.Add(new Vector3(vtx.pos.X - offsetX, vtx.pos.Y - offsetY, 0));
                _uvs.Add(new Vector2(vtx.uv.X, vtx.uv.Y));
                uint col = vtx.col;
                _colors.Add(new Color32(
                    (byte)(col & 0xFF),
                    (byte)((col >> 8) & 0xFF),
                    (byte)((col >> 16) & 0xFF),
                    (byte)((col >> 24) & 0xFF)));
            }

            // Set mesh data
            var mesh = _meshPool[n];
            mesh.Clear();
            mesh.SetVertices(_verts);
            mesh.SetUVs(0, _uvs);
            mesh.SetColors(_colors);
            mesh.subMeshCount = cmdBuffer.Size;

            // Build index data per submesh
            for (int cmd = 0; cmd < cmdBuffer.Size; cmd++)
            {
                var drawCmd = cmdBuffer[cmd];
                _indices.Clear();
                for (int i = 0; i < (int)drawCmd.ElemCount; i++)
                {
                    _indices.Add(idxBuffer[(int)drawCmd.IdxOffset + i] + (int)drawCmd.VtxOffset);
                }
                mesh.SetTriangles(_indices, cmd);
            }
            mesh.UploadMeshData(false);

            // Issue draw commands
            for (int cmd = 0; cmd < cmdBuffer.Size; cmd++)
            {
                var drawCmd = cmdBuffer[cmd];
                if (drawCmd.ElemCount == 0) continue;

                // Scissor rect
                float clipX = drawCmd.ClipRect.X - offsetX;
                float clipY = drawCmd.ClipRect.Y - offsetY;
                float clipW = drawCmd.ClipRect.Z - drawCmd.ClipRect.X;
                float clipH = drawCmd.ClipRect.W - drawCmd.ClipRect.Y;
                _commandBuffer.EnableScissorRect(new Rect(clipX, screenH - clipY - clipH, clipW, clipH));

                // Texture
                _mpb.Clear();
                if (_textures.TryGetValue(drawCmd.TextureId, out var tex))
                {
                    _mpb.SetTexture("_MainTex", tex);
                    _mpb.SetVector("_MainTex_ST", new Vector4(1, -1, 0, 1));
                }
                else
                {
                    _mpb.SetTexture("_MainTex", _fontTexture!);
                    _mpb.SetVector("_MainTex_ST", new Vector4(1, 1, 0, 0));
                }

                _commandBuffer.DrawMesh(mesh, Matrix4x4.identity, _material, cmd, 0, _mpb);
            }
            _commandBuffer.DisableScissorRect();
        }

        Graphics.ExecuteCommandBuffer(_commandBuffer);
    }
}

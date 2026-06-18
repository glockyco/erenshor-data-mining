extern alias Vectors;

using System.Reflection;
using System.Runtime.InteropServices;
using ImGuiNET;
using Lunaris;
using UnityEngine;
using UnityEngine.Rendering;

using ImVec2 = Vectors::System.Numerics.Vector2;

namespace AdventureGuide.Rendering;

/// <summary>
/// Adventure Guide-owned Dear ImGui backend for Unity.
///
/// Lunaris supplies the loaded ImGui.NET/cimgui binaries and plugin lifecycle;
/// Adventure Guide owns a separate ImGui context, font atlas, input pump, and
/// Unity command-buffer renderer. Every frame saves and restores the previous
/// ImGui context so Lunaris and other plugins keep their shared context intact.
/// </summary>
public sealed class ImGuiRenderer : IDisposable
{
    private const float BaseFontSize = 16f;

    private readonly ILog _log;
    private readonly Dictionary<IntPtr, Texture> _textures = new();
    private readonly List<Mesh> _meshPool = new();
    private readonly List<Vector3> _verts = new();
    private readonly List<UnityEngine.Vector2> _uvs = new();
    private readonly List<Color32> _colors = new();
    private readonly List<int> _indices = new();
    private readonly MaterialPropertyBlock _mpb = new();

    private IntPtr _context;
    private Texture2D? _fontTexture;
    private Material? _material;
    private CommandBuffer? _commandBuffer;
    private GCHandle _iniPathHandle;
    private float _uiScale = 1f;
    private float _pendingScale = -1f;
    private byte[]? _unscaledStyleBackup;

    /// <summary>Draw callback invoked between NewFrame and EndFrame.</summary>
    public Action? OnLayout { get; set; }

    /// <summary>True when ImGui wants to capture mouse input.</summary>
    public bool WantCaptureMouse { get; private set; }

    /// <summary>True when an ImGui text input widget is actively being edited.</summary>
    public bool WantTextInput { get; private set; }

    /// <summary>
    /// Absolute path for ImGui's ini persistence file. Set before calling Init().
    /// If null, ImGui's default ini behavior is disabled for this private context.
    /// </summary>
    public string? IniPath { get; set; }

    /// <summary>Set before calling Init(). Scales font and UI element sizes.</summary>
    public float UiScale
    {
        set => _uiScale = value;
    }

    /// <summary>Current effective UI scale factor.</summary>
    public float CurrentScale => _uiScale;

    public ImGuiRenderer(ILog log)
    {
        _log = log;
    }

    /// <summary>
    /// Reset capture flags when ImGui rendering is suppressed, e.g. by F7 UI hide.
    /// </summary>
    internal void ClearCaptureState()
    {
        WantCaptureMouse = false;
        WantTextInput = false;
    }

    /// <summary>
    /// Initialize the private ImGui context, embedded Roboto atlas, and Unity material.
    /// </summary>
    public bool Init()
    {
        if (_context != IntPtr.Zero)
        {
            _log.LogWarning("Adventure Guide ImGuiRenderer.Init() called twice; ignoring.");
            return true;
        }

        var previousContext = ImGui.GetCurrentContext();
        try
        {
            _context = ImGui.CreateContext();
            ImGui.SetCurrentContext(_context);

            var io = ImGui.GetIO();
            io.BackendFlags |= ImGuiBackendFlags.RendererHasVtxOffset;

            ConfigureIni(io);
            ImGui.StyleColorsDark();
            BuildFontAtlas();
            SaveStyleBackup();
            ImGui.GetStyle().ScaleAllSizes(_uiScale);
            CreateMaterial();
            _commandBuffer = new CommandBuffer { name = "AdventureGuide_ImGui" };

            _log.LogInfo("Adventure Guide private ImGui renderer initialized.");
            return true;
        }
        catch (Exception ex)
        {
            _log.LogError($"Adventure Guide ImGui init failed: {ex}");
            DestroyContextIfCreated();
            return false;
        }
        finally
        {
            ImGui.SetCurrentContext(previousContext);
        }
    }

    /// <summary>
    /// Call from the plugin MonoBehaviour's OnGUI(). Handles input, runs layout,
    /// and renders on Unity repaint events.
    /// </summary>
    public void OnGUI()
    {
        if (_context == IntPtr.Zero)
            return;

        var current = Event.current;
        if (current == null || current.type != EventType.Repaint)
            return;

        var previousContext = ImGui.GetCurrentContext();
        ImGui.SetCurrentContext(_context);

        var io = ImGui.GetIO();
        try
        {
            if (_pendingScale >= 0f)
            {
                ApplyScale(_pendingScale);
                _pendingScale = -1f;
            }

            io.DisplaySize = new ImVec2(Screen.width, Screen.height);
            io.DeltaTime = Time.deltaTime > 0f ? Time.deltaTime : 1f / 60f;
            UpdateInput(io);

            ImGui.NewFrame();
            OnLayout?.Invoke();
            ImGui.EndFrame();

            WantCaptureMouse = io.WantCaptureMouse;
            WantTextInput = io.WantTextInput;

            ImGui.Render();
            RenderDrawData();
        }
        catch (Exception ex)
        {
            _log.LogError($"Adventure Guide ImGui render failed: {ex}");
            ClearCaptureState();
        }
        finally
        {
            ImGui.SetCurrentContext(previousContext);
        }
    }

    /// <summary>Register a Unity texture for use as an ImGui texture ID.</summary>
    public IntPtr RegisterTexture(Texture texture)
    {
        var id = texture.GetNativeTexturePtr();
        _textures[id] = texture;
        return id;
    }

    /// <summary>Unregister a previously registered texture.</summary>
    public void UnregisterTexture(IntPtr id) => _textures.Remove(id);

    /// <summary>
    /// Request a scale change. The atlas rebuild is deferred to the next private
    /// render frame so it runs while the Adventure Guide context is current.
    /// </summary>
    public void SetScale(float scale) => _pendingScale = scale;

    /// <summary>
    /// Clear saved ImGui window positions and sizes for this private context.
    /// </summary>
    public void ClearWindowState()
    {
        if (_context == IntPtr.Zero)
            return;

        var previousContext = ImGui.GetCurrentContext();
        try
        {
            ImGui.SetCurrentContext(_context);
            ImGui.LoadIniSettingsFromMemory("");
        }
        finally
        {
            ImGui.SetCurrentContext(previousContext);
        }
    }

    public void Dispose()
    {
        if (_context != IntPtr.Zero)
            DestroyContextIfCreated();

        foreach (var mesh in _meshPool)
            UnityEngine.Object.Destroy(mesh);
        _meshPool.Clear();

        if (_fontTexture != null)
        {
            UnityEngine.Object.Destroy(_fontTexture);
            _fontTexture = null;
        }

        if (_material != null)
        {
            UnityEngine.Object.Destroy(_material);
            _material = null;
        }

        _commandBuffer?.Dispose();
        _commandBuffer = null;
        _textures.Clear();
    }

    private unsafe void ConfigureIni(ImGuiIOPtr io)
    {
        if (IniPath == null)
        {
            io.NativePtr->IniFilename = null;
            return;
        }

        var directory = Path.GetDirectoryName(IniPath);
        if (!string.IsNullOrEmpty(directory))
            Directory.CreateDirectory(directory);

        var pathBytes = System.Text.Encoding.UTF8.GetBytes(IniPath + "\0");
        _iniPathHandle = GCHandle.Alloc(pathBytes, GCHandleType.Pinned);
        io.NativePtr->IniFilename = (byte*)_iniPathHandle.AddrOfPinnedObject();
    }

    private unsafe void BuildFontAtlas()
    {
        var io = ImGui.GetIO();
        var asm = Assembly.GetExecutingAssembly();

        using var fontStream = asm.GetManifestResourceStream("AdventureGuide.Roboto-Regular.ttf");
        if (fontStream != null)
        {
            var fontBytes = new byte[fontStream.Length];
            fontStream.Read(fontBytes, 0, fontBytes.Length);

            var fontPtr = ImGui.MemAlloc((uint)fontBytes.Length);
            Marshal.Copy(fontBytes, 0, fontPtr, fontBytes.Length);

            var builder = new ImFontGlyphRangesBuilderPtr(
                ImGuiNative.ImFontGlyphRangesBuilder_ImFontGlyphRangesBuilder()
            );
            builder.AddRanges(io.Fonts.GetGlyphRangesDefault());
            builder.AddChar('\u2713');
            builder.AddChar('\u25cb');
            builder.BuildRanges(out ImVector ranges);

            var configPtr = ImGuiNative.ImFontConfig_ImFontConfig();
            configPtr->OversampleH = 2;
            configPtr->OversampleV = 1;

            io.Fonts.AddFontFromMemoryTTF(
                fontPtr,
                fontBytes.Length,
                BaseFontSize * _uiScale,
                (ImFontConfigPtr)configPtr,
                ranges.Data
            );

            builder.Destroy();
        }
        else
        {
            _log.LogWarning(
                "AdventureGuide.Roboto-Regular.ttf not found; using ImGui default font."
            );
            io.Fonts.AddFontDefault();
        }

        io.Fonts.Build();
        io.Fonts.GetTexDataAsRGBA32(out byte* pixels, out int width, out int height, out int _);
        if (pixels == null || width <= 0 || height <= 0)
            throw new InvalidOperationException(
                "Adventure Guide font atlas built with no texture data."
            );

        _fontTexture = new Texture2D(width, height, TextureFormat.RGBA32, false);
        var data = new byte[width * height * 4];
        Marshal.Copy((IntPtr)pixels, data, 0, data.Length);
        _fontTexture.LoadRawTextureData(data);
        _fontTexture.Apply();

        io.Fonts.SetTexID(_fontTexture.GetNativeTexturePtr());
    }

    private unsafe void ApplyScale(float newScale)
    {
        _uiScale = newScale;

        if (_fontTexture != null)
        {
            UnityEngine.Object.Destroy(_fontTexture);
            _fontTexture = null;
        }

        var io = ImGui.GetIO();
        io.Fonts.Clear();
        BuildFontAtlas();

        RestoreStyleBackup();
        ImGui.GetStyle().ScaleAllSizes(_uiScale);

        if (_material != null)
            _material.mainTexture = _fontTexture;

        _log.LogInfo($"Adventure Guide UI scale changed to {_uiScale:F2}.");
    }

    private unsafe void SaveStyleBackup()
    {
        int size = sizeof(ImGuiStyle);
        _unscaledStyleBackup = new byte[size];
        fixed (byte* dst = _unscaledStyleBackup)
            Buffer.MemoryCopy(ImGui.GetStyle().NativePtr, dst, size, size);
    }

    private unsafe void RestoreStyleBackup()
    {
        if (_unscaledStyleBackup == null)
            return;

        fixed (byte* src = _unscaledStyleBackup)
            Buffer.MemoryCopy(
                src,
                ImGui.GetStyle().NativePtr,
                _unscaledStyleBackup.Length,
                _unscaledStyleBackup.Length
            );
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
        var mousePos = Input.mousePosition;
        io.AddMousePosEvent(mousePos.x, Screen.height - mousePos.y);

        io.AddMouseButtonEvent(0, Input.GetMouseButton(0));
        io.AddMouseButtonEvent(1, Input.GetMouseButton(1));
        io.AddMouseButtonEvent(2, Input.GetMouseButton(2));

        var scroll = Input.mouseScrollDelta;
        if (scroll.y != 0f || scroll.x != 0f)
            io.AddMouseWheelEvent(scroll.x, scroll.y);

        io.AddKeyEvent(
            (ImGuiKey)641,
            Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl)
        );
        io.AddKeyEvent(
            (ImGuiKey)642,
            Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift)
        );
        io.AddKeyEvent(
            (ImGuiKey)643,
            Input.GetKey(KeyCode.LeftAlt) || Input.GetKey(KeyCode.RightAlt)
        );

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

    private unsafe void RenderDrawData()
    {
        if (_commandBuffer == null || _material == null)
            return;

        var drawData = ImGui.GetDrawData();
        if (drawData.CmdListsCount == 0)
            return;

        float screenW = Screen.width;
        float screenH = Screen.height;
        var projection = Matrix4x4.Ortho(0f, screenW, screenH, 0f, -1f, 1f);

        _commandBuffer.Clear();
        _commandBuffer.SetProjectionMatrix(projection);
        _commandBuffer.SetViewMatrix(Matrix4x4.identity);

        float offsetX = drawData.DisplayPos.X;
        float offsetY = drawData.DisplayPos.Y;

        while (_meshPool.Count < drawData.CmdListsCount)
        {
            var mesh = new Mesh { indexFormat = IndexFormat.UInt32 };
            mesh.MarkDynamic();
            _meshPool.Add(mesh);
        }

        for (int n = 0; n < drawData.CmdListsCount; n++)
        {
            var cmdList = drawData.CmdListsRange[n];
            var vtxBuffer = cmdList.VtxBuffer;
            var idxBuffer = cmdList.IdxBuffer;
            var cmdBuffer = cmdList.CmdBuffer;

            _verts.Clear();
            _uvs.Clear();
            _colors.Clear();

            for (int v = 0; v < vtxBuffer.Size; v++)
            {
                var vtx = vtxBuffer[v];
                _verts.Add(new Vector3(vtx.pos.X - offsetX, vtx.pos.Y - offsetY, 0f));
                _uvs.Add(new UnityEngine.Vector2(vtx.uv.X, vtx.uv.Y));
                uint color = vtx.col;
                _colors.Add(
                    new Color32(
                        (byte)(color & 0xFF),
                        (byte)((color >> 8) & 0xFF),
                        (byte)((color >> 16) & 0xFF),
                        (byte)((color >> 24) & 0xFF)
                    )
                );
            }

            var mesh = _meshPool[n];
            mesh.Clear();
            mesh.SetVertices(_verts);
            mesh.SetUVs(0, _uvs);
            mesh.SetColors(_colors);
            mesh.subMeshCount = cmdBuffer.Size;

            for (int cmd = 0; cmd < cmdBuffer.Size; cmd++)
            {
                var drawCmd = cmdBuffer[cmd];
                _indices.Clear();
                for (int i = 0; i < (int)drawCmd.ElemCount; i++)
                    _indices.Add(idxBuffer[(int)drawCmd.IdxOffset + i] + (int)drawCmd.VtxOffset);
                mesh.SetTriangles(_indices, cmd);
            }
            mesh.UploadMeshData(false);

            for (int cmd = 0; cmd < cmdBuffer.Size; cmd++)
            {
                var drawCmd = cmdBuffer[cmd];
                if (drawCmd.ElemCount == 0)
                    continue;

                float clipX = drawCmd.ClipRect.X - offsetX;
                float clipY = drawCmd.ClipRect.Y - offsetY;
                float clipW = drawCmd.ClipRect.Z - drawCmd.ClipRect.X;
                float clipH = drawCmd.ClipRect.W - drawCmd.ClipRect.Y;
                _commandBuffer.EnableScissorRect(
                    new Rect(clipX, screenH - clipY - clipH, clipW, clipH)
                );

                _mpb.Clear();
                if (_textures.TryGetValue(drawCmd.TextureId, out var texture))
                {
                    _mpb.SetTexture("_MainTex", texture);
                    _mpb.SetVector("_MainTex_ST", new Vector4(1f, -1f, 0f, 1f));
                }
                else
                {
                    _mpb.SetTexture("_MainTex", _fontTexture!);
                    _mpb.SetVector("_MainTex_ST", new Vector4(1f, 1f, 0f, 0f));
                }

                _commandBuffer.DrawMesh(mesh, Matrix4x4.identity, _material, cmd, 0, _mpb);
            }
            _commandBuffer.DisableScissorRect();
        }

        Graphics.ExecuteCommandBuffer(_commandBuffer);
    }

    private void DestroyContextIfCreated()
    {
        if (_iniPathHandle.IsAllocated)
            _iniPathHandle.Free();

        if (_context == IntPtr.Zero)
            return;

        var previousContext = ImGui.GetCurrentContext();
        if (previousContext == _context)
            previousContext = IntPtr.Zero;

        try
        {
            ImGui.SetCurrentContext(_context);
            ImGui.DestroyContext(_context);
        }
        finally
        {
            _context = IntPtr.Zero;
            ImGui.SetCurrentContext(previousContext);
        }
    }
}

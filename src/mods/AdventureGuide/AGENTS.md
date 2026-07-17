# Adventure Guide Agent Notes

Adventure Guide has native BepInEx and Lunaris entrypoints over one shared
runtime ported from the stable UI. Keep the shared UI and behavior consistent
across loaders unless the user explicitly approves a change.

## Loader and rendering boundaries

- `Plugin.BepInEx.cs` and `Plugin.Lunaris.cs` are thin loader adapters. Shared
  lifecycle, state, rendering, and cleanup stay in `Plugin.cs`.
- Adventure Guide owns a private ImGui context, font atlas, input pump, and Unity
  `CommandBuffer` renderer in `src/Rendering/ImGuiRenderer.cs`.
- The Lunaris target uses Lunaris-provided `ImGui.NET.dll` and `cimgui`. The
  BepInEx target uses the official `ImGui.NET` NuGet package and ships its
  managed and Windows x64 native runtime files through `thunderstore.toml`.
  Never check in, extract, or load private ImGui binaries.
- Do not use `Lunaris.IGUI.ImGuiEx.RegisterFont` for Adventure Guide Roboto. Roboto is an embedded `AdventureGuide.Roboto-Regular.ttf` resource loaded into the private atlas with `ImGui.MemAlloc` and `AddFontFromMemoryTTF`.
- Do not draw Adventure Guide UI from `OnImGuiDraw()`. `Plugin.OnGUI()` must call the private renderer, and the renderer must set `ImGui.SetCurrentContext(_context)` for the entire frame before restoring the previous context in `finally`.
- Keep private `ImGuiIO.DisplaySize` equal to `Screen.width`/`Screen.height`. The guide windows, tracker backdrop, and arrow overlays share full-screen ImGui draw lists and screen-space camera projections.
- Scope Adventure Guide window styling with `Theme.WindowStyleScope()`. Pair every `ImGui.Begin(...)` with `ImGui.End()` in a `finally` block, even when `Begin` returns `false`.
- Do not add Adventure Guide workarounds for Lunaris-wide keyboard capture while a Lunaris-owned ImGui window is hovered. That behavior affects all mods and belongs upstream in Lunaris.

## Lunaris API references

- Docs: `https://mizukibelhi.github.io/Lunaris-Docs/`
- Plugins extend `LunarisPlugin` and use `[LunarisPlugin("ModName", "SemVerVersion", "AuthorName", "ShortDescription")]`.
- Lunaris can reload plugins when `plugins/<Mod>.dll` changes; cleanup in `OnDestroy()` must assume runtime unload/reload.
- Preferred config shape is `Config.Register<T>()` with `[Config]`, `[ConfigSection]`, `[Keybind]`, and related attributes. Use the low-level `Read`/`Write`/`OnChanged` API only when Adventure Guide's per-character dynamic keys require it.

## Cleanup checklist

`Plugin.OnDestroy()` must detach scene/config handlers, unpatch Harmony, dispose tracker/window/private renderer resources, clear patch statics and debug API statics, release marker fonts, invalidate camera/overlap caches, and reset `GameData.PlayerTyping` if Adventure Guide set it.

## Verification loop

Use focused checks while editing:

```bash
uv run pytest tests/unit/mods/test_adventure_guide_lunaris.py tests/unit/mods/test_adventure_guide_style.py tests/unit/mods/test_adventure_guide_shortcuts.py tests/unit/mods/test_adventure_guide_quest_list.py tests/unit/mods/test_adventure_guide_font.py tests/unit/mods/test_adventure_guide_renderer.py tests/unit/mods/test_adventure_guide_vault.py tests/unit/cli/commands/test_mod.py
uv run erenshor mod build --mod adventure-guide --loader all
```

Native Lunaris Playtest deployment requires a full Playtest restart. Replacing `plugins/AdventureGuide.dll` does not hot-reload the mod in a running game.

## Distribution

Adventure Guide ships as a BepInEx package on Thunderstore and a native Lunaris
release through the Erenshor Vault. Thunderstore packaging is defined by
`thunderstore.toml`. Vault listing assets and the manual upload workflow live in
`vault/` — see `vault/AGENTS.md`. The Vault package ships only
`AdventureGuide.dll`; Lunaris provides the shared dependencies.

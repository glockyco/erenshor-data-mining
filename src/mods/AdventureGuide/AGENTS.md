# Adventure Guide Agent Notes

Adventure Guide is a native Lunaris plugin ported from the stable Thunderstore-era UI. Keep the stable UI and behavior unless the user explicitly approves a change.

## Lunaris boundaries

- Adventure Guide is a native `LunarisPlugin`, but it owns a private ImGui context, font atlas, input pump, and Unity `CommandBuffer` renderer in `src/Rendering/ImGuiRenderer.cs`.
- Use Lunaris-provided `ImGui.NET.dll` and `cimgui` only. Never ship, embed, extract, load, or ILRepack private ImGui managed/native binaries for Adventure Guide.
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
uv run erenshor mod build --mod adventure-guide
```

Native Lunaris Playtest deployment requires a full Playtest restart. Replacing `plugins/AdventureGuide.dll` does not hot-reload the mod in a running game.

## Distribution

Adventure Guide ships through the Erenshor Vault (Lunaris), not Thunderstore.
Listing assets (`vault.toml`, `README.md`, `CHANGELOG.md`, `icon.png`) and the
publish/version workflow live in `vault/` — see `vault/AGENTS.md`. The Vault
package ships only `AdventureGuide.dll`; Lunaris provides the shared deps.

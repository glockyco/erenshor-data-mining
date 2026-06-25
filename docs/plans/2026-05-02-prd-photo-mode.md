# Erenshor Photo Mode - Implementation Plan

**Created:** February 13, 2026
**Project:** Standalone BepInEx mod for Erenshor
**Related:** Separate from "Justice for F7" UI hiding mod

---

## Executive Summary

**Overall Feasibility: EXCELLENT**

All requested features are fully achievable:
- Free camera (game already has `DroneCam.cs` implementation!)
- Freeze/pause scene (`Time.timeScale = 0`)
- FOV/roll/zoom controls (FOV already exposed via `GameData.FOV`)
- Post-processing (Unity PP Stack v2 installed, many effects ready)
- Hide player (modular mesh system, easy to toggle)
- Time/lighting controls (comprehensive day/night + weather systems)

**Total Estimated Time:** 40-60 hours for full-featured photo mode

---

## Feature Feasibility Matrix

| Feature | Difficulty | Time | Notes |
|---------|-----------|------|-------|
| **Free camera** | Easy | 4-6h | `DroneCam.cs` exists, needs mouse look + toggle |
| **Time freeze** | Very Easy | 0.5h | `Time.timeScale = 0` (one line!) |
| **FOV control** | Easy | 1h | `GameData.FOV` already exists |
| **Zoom** | Easy | 1h | Position or FOV modification |
| **Roll** | Easy | 1h | Z-axis rotation (need to remove lock) |
| **Hide UI** | Easy | 1h | `GameData.MainCanvas.enabled = false` |
| **Hide player** | Easy | 2h | `modularPar.AllBase.SetActive(false)` |
| **Time of day** | Easy | 4-6h | `GameData.Time.hour/min`, presets + UI |
| **Weather** | Easy | 2-4h | `GameData.Atmos.Cloudiness/isRaining` |
| **Sun angle** | Easy | 2-3h | `GameData.Time.SunParent.eulerAngles` |
| **Lighting colors** | Easy | 3-4h | `RenderSettings.ambientLight`, skybox colors |
| **Vignette** | Very Easy | 0.5h | Already configured, just enable |
| **Chromatic Aberration** | Very Easy | 0.5h | Already configured, just enable |
| **Bloom/Color Grading** | Easy | 2h | Already active, expose controls |
| **Depth of Field** | Medium | 6-8h | Shader exists, needs adding + tuning |
| **Film Grain** | Medium | 3-4h | Shader exists, needs adding |
| **Screenshot** | Easy | 2-3h | Unity `ScreenCapture` API + resolution multiplier |
| **Preset system** | Medium | 4-6h | Save/load camera+lighting+PP state |

---

## Key Research Findings

### 1. Camera System

**Main Controller:** `CameraController.cs` (603 lines)
- Uses Cinemachine (`CinemachineVirtualCamera` + `CinemachineOrbitalTransposer`)
- Has TPV (third-person), FPV (first-person), and **DroneCam** (free-fly) modes
- **DroneCam is already implemented but disabled!**

**DroneCam.cs (175 lines):**
```csharp
// Already has:
// - WASD movement with acceleration
// - Arrow key pitch/yaw
// - Space/Shift for up/down
// - Home key to teleport to player
// Just needs:
// - Mouse look (currently arrow keys)
// - Toggle activation
```

**To detach from player:**
```csharp
CameraController camController = mainCamera.GetComponent<CameraController>();
camController.enabled = false;  // Disables Cinemachine control
GameData.PlayerTyping = true;   // Blocks player inpu
```

**FOV:** `GameData.FOV` (default 60, already in options menu)

---

### 2. Time Freeze

**One line of code:**
```csharp
Time.timeScale = 0f;  // Freeze
Time.timeScale = 1f;  // Resume
```

**Why it works:**
- All game logic: `someValue -= 60f * Time.deltaTime`
- NavMeshAgent (NPC movement): Respects timeScale
- Animator (animations): Respects timeScale
- ParticleSystem (effects): Respects timeScale
- No multiplayer complications (single-player game)

---

### 3. Post-Processing

**Stack:** Unity Post Processing Stack v2, installed and active

**Current Profile (`Main Camera Profile.asset`):**
- **Bloom** - Active (intensity 9, user-adjustable)
- **Ambient Occlusion** - Active (intensity 0.13)
- **Color Grading** - Active (temp/sat/contrast/brightness in options)
- **Vignette** - Configured but disabled (intensity 0.263, ready to enable!)
- **Chromatic Aberration** - Configured but disabled (ready to enable!)
- **Depth of Field** - Shader exists, not in profile (needs adding)
- **Film Grain** - Shader exists, not in profile (needs adding)

**Access at runtime:**
```csharp
PostProcessProfile profile = GameData.CamGetPPFX.GetLivePPFX();

// Enable vignette (trivial)
if (profile.TryGetSettings<Vignette>(out var vignette))
{
    vignette.active = true;
    vignette.intensity.value = 0.3f;
}
```

---

### 4. Player Hiding

**Player Structure:**
- `PlayerControl` component on root GameObjec
- `ModularPar` child with Male/Female `ModularParts`
- Each body part has `SkinnedMeshRenderer`
- Separate `NamePlate` GameObjec

**Hide implementation:**
```csharp
ModularPar modularPar = GameData.PlayerControl.GetComponentInChildren<ModularPar>();
modularPar.AllBase.SetActive(false);  // Hides all body parts
GameData.PlayerControl.NamePlate.gameObject.SetActive(false);
```

---

### 5. Time of Day and Lighting

**Day/Night System:** `DayNight.cs`
- Fully dynamic cycle
- `public int hour` (0-23), `public int min` (0-59)
- `public int TimeScale` - Speed multiplier (0 = freeze)
- `public Transform SunParent` - Sun rotation control
- `public Light Sun` - Directional ligh
- Globally accessible: `GameData.Time`

**Lighting Controller:** `AtmosphereColors.cs`
- Sky colors (day/night, clouds, horizon)
- Ambient lighting (`RenderSettings.ambientLight`)
- Weather (cloudiness, rain, lightning)
- Fog (distance, density, color)

**Controllable at runtime:**
```csharp
// Time
GameData.Time.hour = 19;              // Golden hour
GameData.Time.TimeScale = 0;          // Freeze time

// Sun
GameData.Time.SunParent.localEulerAngles = new Vector3(0, yaw, pitch);
GameData.Time.Sun.color = Color.yellow;

// Weather
GameData.Atmos.Cloudiness = 0.3f;     // 0-0.8
GameData.Atmos.isRaining = true;
GameData.Atmos.Rain.SetActive(true);
GameData.Atmos.Lightning.SetActive(true);

// Lighting
RenderSettings.ambientLight = Color.gray;
RenderSettings.fogStartDistance = 50f;
RenderSettings.fogEndDistance = 500f;

// Apply immediately (skip lerp)
GameData.Atmos.ForceColors();
```

**Debug commands exist:**
- `/time` - Show current time
- `/time10` - 10x speed
- `/time50` - 50x speed

---

## Implementation Plan

### Phase 1: Core Photo Mode (12-16 hours)

**MVP Features:**
- Free-fly camera (WASD + mouse look)
- Toggle hotkey (F9)
- Time freeze (T key)
- Hide UI (H key)
- Hide player (P key)
- FOV control (mouse wheel)
- Movement speed (Shift = fast, Ctrl = slow)

**Architecture:**
```
src/mods/PhotoMode/
├── PhotoMode.csproj
├── src/
│   ├── Plugin.cs                 // BepInEx entry poin
│   ├── PluginInfo.cs             // GUID, version
│   ├── PhotoModeController.cs    // Core photo mode logic
│   ├── CameraState.cs            // Save/restore camera state
│   └── Patches/
│       └── TypeTextPatch.cs      // Capture F9 before game
└── thunderstore/
    ├── icon.png
    ├── README.md
    └── manifest.json
```

**Dependencies:**
- BepInEx 5
- HarmonyX 2.16.0
- UnityEngine.CoreModule
- UnityEngine.InputLegacyModule

---

### Phase 2: Camera Enhancements (6-8 hours)

**Features:**
- Roll control (Q/E keys)
- Zoom presets (1-4 keys: 60/80/100/120 FOV)
- On-screen info display (position, rotation, FOV, time)
- Reset to player (Home key)
- Camera collision toggle (clip through walls)

---

### Phase 3: Lighting and Time (10-14 hours)

**Features:**
- Time of day presets (Dawn/Morning/Noon/Sunset/Night/Custom)
- Hour/minute sliders
- Sun rotation control (pitch/yaw sliders)
- Sun color picker
- Ambient color picker
- Weather presets (Clear/Cloudy/Overcast/Rain/Storm)
- Cloudiness slider (0-0.8)
- Fog distance sliders (near/far)
- Fog toggle

**UI Approach Options:**

**A. BepInEx Config (Simpler, recommended for initial release):**
```ini
[Time]
Hour = 19
Minute = 30
FreezeTime = true

[Weather]
Cloudiness = 0.3
Rain = false
Lightning = false

[Sun]
Pitch = 15.0
Yaw = 45.0
```

**B. ImGui UI (More polished, recommended for v2.0):**
- Runtime UI with sliders, color pickers, buttons
- Requires `UnityEngine.IMGUIModule.dll`
- More intuitive but more dev time

---

### Phase 4: Post-Processing (8-12 hours)

**Features:**
- Vignette control (intensity/smoothness sliders)
- Chromatic aberration toggle + intensity
- Depth of field (focus distance/aperture/auto-focus)
- Bloom intensity override
- Color grading presets (Vibrant/Vintage/Noir/Cinematic)
- Saturation/contrast/brightness sliders
- Film grain toggle (if added)

**Challenge:** DoF needs tuning for game's art style (4-6 hours of tweaking)

---

### Phase 5: Polish (4-6 hours)

**Features:**
- Screenshot hotkey (Enter key) with 2x/4x resolution multiplier
- Grid overlay (rule of thirds, center cross)
- Safe zone guides (16:9, 4:3, 21:9)
- Preset save/load (save camera+lighting+PP as named preset)
- Help overlay (key bindings)

---

## Technical Challenges and Solutions

### Challenge 1: Cinemachine Override

**Problem:** `CinemachineVirtualCamera` fights for camera control

**Solution:**
```csharp
CameraController camController = mainCamera.GetComponent<CameraController>();
camController.enabled = false;  // Cleanest approach
```

---

### Challenge 2: Input Conflicts

**Problem:** WASD moves player, not camera

**Solution:**
```csharp
GameData.PlayerTyping = true;  // Game thinks you're typing, blocks movemen
```

---

### Challenge 3: AtmosphereColors Override

**Problem:** `AtmosphereColors.Update()` continuously lerps colors, overriding
manual changes

**Solutions:**
1. `Time.timeScale = 0` stops lerping (uses `Time.deltaTime`)
2. `GameData.Atmos.enabled = false` disables componen
3. Call `GameData.Atmos.ForceColors()` to skip lerp

**Recommended:** Use TimeScale=0 when time frozen, otherwise disable componen

---

### Challenge 4: State Restoration

**Problem:** Need to restore camera, lighting, PP on exi

**Solution:** State snapshot classes

```csharp
public class CameraState
{
    public Vector3 position;
    public Quaternion rotation;
    public float fov;
    public bool cameraControllerEnabled;

    public static CameraState Capture() { ... }
    public void Restore() { ... }
}
```

Same pattern for `LightingState` and `PostProcessingState`.

---

## BepInEx Configuration

**Config file:** `BepInEx/config/wow-much.photo-mode.cfg`

```ini
[Hotkeys]
Toggle = F9
FreezeTime = T
HideUI = H
HidePlayer = P
Screenshot = Return

[Camera]
MoveSpeed = 10.0
LookSpeed = 2.0
FastSpeedMultiplier = 3.0
SlowSpeedMultiplier = 0.3
EnableRoll = true

[Features]
EnableDepthOfField = true
EnableVignette = true
EnableChromaticAberration = false
ScreenshotResolutionMultiplier = 2

[Time]
DefaultHour = 19
DefaultMinute = 30
FreezeTimeOnActivate = false

[Weather]
DefaultCloudiness = 0.3
DefaultRain = false
```

---

## Mod Metadata

**Plugin Info:**
```csharp
[BepInPlugin("wow-much.photo-mode", "Photo Mode", "2026.213.0")]
[BepInProcess("Erenshor.exe")]
public class PhotoModePlugin : BaseUnityPlugin
```

**Thunderstore:**
- Namespace: `WoW_Much`
- Package: `PhotoMode`
- Dependency: `BepInEx-BepInExPack-5.4.21`

---

## Timeline Estimate

| Phase | Features | Hours | Cumulative |
|-------|----------|-------|------------|
| 1 | Core photo mode | 12-16 | 12-16 |
| 2 | Camera enhancements | 6-8 | 18-24 |
| 3 | Lighting and time | 10-14 | 28-38 |
| 4 | Post-processing | 8-12 | 36-50 |
| 5 | Polish | 4-6 | 40-56 |

---

## Open Questions

1. **UI Preference:** BepInEx config (hotkeys only) or ImGui (sliders/pickers)?
2. **Priority:** Any features more important than others?
3. **Icon/Branding:** Any specific visual theme for Thunderstore page?

---

## Decompiled Source References (Read-Only)

- `CameraController.cs` - Main camera with Cinemachine
- `DroneCam.cs` - Existing free-fly camera implementation
- `FPVCam.cs` - First-person camera
- `CamOptionsListener.cs` - FOV application
- `CamGetPPFXProfile.cs` - Post-processing profile access
- `ApplyOptions.cs` - PP volume reference
- `DayNight.cs` - Time of day system
- `AtmosphereColors.cs` - Sky, weather, fog, ambient lighting
- `WeatherTrend.cs` - Zone weather constraints
- `PlayerControl.cs` - Player character
- `ModularPar.cs` / `ModularParts.cs` - Player mesh system
- `Character.cs` - Base character class
- `NPC.cs` - NPC behavior and animation
- `SimPlayer.cs` - Simulated player behavior
- `TypeText.cs` - Input handling, debug commands
- `GameData.cs` - Static global references

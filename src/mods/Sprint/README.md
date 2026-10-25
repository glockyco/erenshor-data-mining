# Sprint

Sprint adds a configurable sprint key to Erenshor. Use it to move your character faster while exploring, either by holding a key or toggling sprint on and off.

## Install and use

Choose the release for your loader:

- [BepInEx installation and controls](thunderstore/README.md).
- [Lunaris installation and controls](vault/README.md).

Hold Left Shift to sprint with the initial settings. Sprint affects only your character and applies its multiplier after movement buffs and debuffs. Change the key, toggle mode and multiplier through your loader's configuration.

## Build and deploy

Follow the [repository setup](../../../README.md#setup) first. From the repository root, with the game closed:

```sh
uv run erenshor mod setup
uv run erenshor mod build --mod sprint --loader bepinex
uv run erenshor mod deploy --mod sprint --loader bepinex
```

Use `--loader lunaris` instead for the Lunaris build. Deployment installs the selected artifact and activates its loader. Restart the game after deployment. Do not put one loader's DLL into the other loader's plugin directory.

## Development and releases

[src/Core/SprintRuntime.cs](src/Core/SprintRuntime.cs) holds the shared sprint lifecycle. The loader adapters bind controls and settings.

The [mod-development guide](../../../.agent/skills/mod-development/SKILL.md) covers local development. The [mod-pipeline guide](../../../.agent/skills/mod-pipeline/SKILL.md) covers packaging and publishing. Run checks through the repository's `erenshor test` commands, as described in the [repository README](../../../README.md#working-on-it).

## License

[MIT](../../../LICENSE).

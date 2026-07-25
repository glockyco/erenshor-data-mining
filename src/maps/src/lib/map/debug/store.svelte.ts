import type { PositionOverrides } from './persistence';
import type { BackdropSettings } from './backdrop-persistence';

const DEFAULT_BACKDROP: BackdropSettings = {
    enabled: true,
    x: 0,
    y: 0,
    scale: 13
};

export interface DebugStoreState {
    enabled: boolean;
    overrides: PositionOverrides;
    draggingZone: string | null;
    backdrop: BackdropSettings;
}

export interface DebugStore {
    readonly enabled: boolean;
    readonly overrides: PositionOverrides;
    readonly draggingZone: string | null;
    readonly backdrop: BackdropSettings;
    enable(): void;
    disable(): void;
    setOverride(zoneKey: string, pos: { worldX: number; worldY: number }): void;
    setDraggingZone(zoneKey: string | null): void;
    setBackdrop(settings: Partial<BackdropSettings>): void;
    resetBackdrop(): void;
    reset(): void;
}

export function createDebugStore(
    initialOverrides: PositionOverrides = {},
    initialBackdrop: BackdropSettings = DEFAULT_BACKDROP
): DebugStore {
    let enabled = $state(false);
    let overrides = $state<PositionOverrides>(initialOverrides);
    let draggingZone = $state<string | null>(null);
    let backdrop = $state<BackdropSettings>({ ...DEFAULT_BACKDROP, ...initialBackdrop });

    return {
        get enabled() {
            return enabled;
        },
        get overrides() {
            return overrides;
        },
        get draggingZone() {
            return draggingZone;
        },
        get backdrop() {
            return backdrop;
        },

        enable() {
            enabled = true;
        },

        disable() {
            enabled = false;
        },

        setOverride(zoneKey: string, pos: { worldX: number; worldY: number }) {
            overrides = { ...overrides, [zoneKey]: pos };
        },

        setDraggingZone(zoneKey: string | null) {
            draggingZone = zoneKey;
        },

        setBackdrop(settings: Partial<BackdropSettings>) {
            backdrop = { ...backdrop, ...settings };
        },

        resetBackdrop() {
            backdrop = { ...DEFAULT_BACKDROP };
        },

        reset() {
            overrides = {};
        }
    };
}

export type DebugStoreInstance = ReturnType<typeof createDebugStore>;

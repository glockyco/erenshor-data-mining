export type PositionOverrides = Record<string, { worldX: number; worldY: number }>;

const STORAGE_KEY = 'erenshor-map-zone-overrides';

export function loadOverrides(): PositionOverrides {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return {};
        return JSON.parse(stored);
    } catch {
        return {};
    }
}

export function saveOverrides(overrides: PositionOverrides): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
    } catch (e) {
        console.error('Failed to save zone overrides:', e);
    }
}

export function clearOverrides(): void {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
        console.error('Failed to clear zone overrides:', e);
    }
}

export interface BackdropSettings {
    enabled: boolean;
    x: number;
    y: number;
    scale: number;
}

const STORAGE_KEY = 'erenshor-map-backdrop';

const DEFAULTS: BackdropSettings = {
    enabled: true,
    x: 0,
    y: 0,
    scale: 13
};

export function loadBackdropSettings(): BackdropSettings {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return { ...DEFAULTS };
        return { ...DEFAULTS, ...JSON.parse(stored) };
    } catch {
        return { ...DEFAULTS };
    }
}

export function saveBackdropSettings(settings: BackdropSettings): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
        console.warn('Failed to save backdrop settings to localStorage');
    }
}

export function clearBackdropSettings(): void {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch {
        console.warn('Failed to clear backdrop settings from localStorage');
    }
}

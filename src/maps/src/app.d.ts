// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
    namespace App {
        // interface Error {}
        // interface Locals {}
        // interface PageData {}
        // interface PageState {}
        // interface Platform {}
    }
}

// Leaflet rotate extension (augments Leaflet types)
declare module 'leaflet' {
    interface MapOptions {
        rotate?: boolean;
        bearing?: number;
        rotateControl?: boolean;
        touchRotate?: boolean;
        shiftKeyRotate?: boolean;
        bearingSnap?: number;
    }
    interface Map {
        setBearing(bearing: number, options?: { animate?: boolean; duration?: number }): this;
    }
}

export {};

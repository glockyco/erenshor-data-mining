import type { ConnectionState, LiveMode } from '$lib/map/live';

/** Lime when live data arrives, amber while connecting, grey when Live is off. */
export function liveStatusColor(mode: LiveMode, connectionState: ConnectionState): string {
    if (mode === 'off') return '#71717a';
    return connectionState === 'connected' ? '#a3e635' : '#facc15';
}

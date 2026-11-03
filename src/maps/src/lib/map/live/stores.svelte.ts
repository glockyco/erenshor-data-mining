/**
 * Svelte 5 reactive state for live entity data from InteractiveMapCompanion mod.
 *
 * Uses runes ($state) for reactive state management.
 * Singleton pattern - all components share the same connection.
 */

import { browser } from '$app/environment';
import { LiveConnection, LOCAL_SERVER_URL, WebRtcTransport, WebSocketTransport } from './connection';
import { formatPairing, parsePairing, parsePairingHash, type PairingLink } from './pairing';
import type { LiveState, EntityData, ProtocolMessage, SharingStatus } from './types';

/**
 * Where the map gets live data from: nowhere, the mod on this PC, or the mod on the
 * PC a pairing link named.
 */
export type LiveMode = 'off' | 'local' | 'paired';

/** 'true' while the map connects to the mod on this PC */
const LOCAL_MODE_KEY = 'erenshor-map-live-mode';
/** The pairing this device connects with */
const PAIRING_KEY = 'erenshor-map-live-pairing';

const INITIAL_STATE: LiveState = {
    connectionState: 'disconnected',
    zone: null,
    entities: [],
    capabilities: [],
    protocolVersion: null,
    modVersion: null,
    lastUpdate: null,
    sharing: null
};

// Module-level reactive state using $state rune
const state = $state<LiveState>({ ...INITIAL_STATE });
const session = $state<{ mode: LiveMode; pairing: PairingLink | null }>({
    mode: 'off',
    pairing: null
});
// When this device started waiting for the game, and when sharing last had no viewer,
// so the panel can say what to check however long it has been closed.
const timing = $state<{ waitingSince: number | null; sharingIdleSince: number | null }>({
    waitingSince: null,
    sharingIdleSince: null
});

// Singleton connection instance
let connection: LiveConnection | null = null;

function getConnection(): LiveConnection {
    if (!connection) {
        connection = new LiveConnection(
            (connectionState) => {
                state.connectionState = connectionState;

                if (connectionState === 'connected') {
                    timing.waitingSince = null;
                } else if (session.mode !== 'off' && timing.waitingSince === null) {
                    timing.waitingSince = Date.now();
                }

                // Clear entities when disconnected or reconnecting
                if (connectionState === 'disconnected' || connectionState === 'reconnecting') {
                    state.entities = [];
                    setSharing(null);
                }
            },
            (message) => {
                handleMessage(message);
            }
        );
    }
    return connection;
}

function setSharing(sharing: SharingStatus | null): void {
    state.sharing = sharing;
    const idle = !!sharing?.enabled && sharing.viewers === 0;
    if (!idle) timing.sharingIdleSince = null;
    else if (timing.sharingIdleSince === null) timing.sharingIdleSince = Date.now();
}

function handleMessage(message: ProtocolMessage): void {
    switch (message.type) {
        case 'handshake':
            state.zone = message.zone;
            state.capabilities = message.capabilities;
            state.protocolVersion = message.protocolVersion;
            state.modVersion = message.modVersion;
            setSharing(message.sharing ?? null);
            break;

        case 'sharingChanged':
            setSharing(message.sharing);
            break;

        case 'stateUpdate':
            state.zone = message.zone;
            state.entities = message.entities;
            state.lastUpdate = message.timestamp;
            break;

        case 'zoneChange':
            state.zone = message.zone;
            state.entities = [];
            break;
    }
}

function resetState(): void {
    Object.assign(state, INITIAL_STATE);
}

function readStorage(key: string): string | null {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function writeStorage(key: string, value: string | null): void {
    try {
        if (value === null) localStorage.removeItem(key);
        else localStorage.setItem(key, value);
    } catch {
        // Storage can be unavailable in private windows; the choice lasts for this visit.
    }
}

function startLocal(): void {
    session.mode = 'local';
    session.pairing = null;
    timing.waitingSince = null;
    getConnection().connect(() => new WebSocketTransport(LOCAL_SERVER_URL));
}

function startPaired(pairing: PairingLink): void {
    session.mode = 'paired';
    session.pairing = pairing;
    timing.waitingSince = null;
    getConnection().connect(() => new WebRtcTransport(pairing));
}

function stop(): void {
    session.mode = 'off';
    session.pairing = null;
    getConnection().disconnect();
    timing.waitingSince = null;
    timing.sharingIdleSince = null;
    resetState();
}

/**
 * Live state - reactive access to all live data.
 * Access properties directly; they're reactive in Svelte 5 contexts.
 */
export const liveState = {
    get connectionState() {
        return state.connectionState;
    },
    get zone() {
        return state.zone;
    },
    get entities() {
        return state.entities;
    },
    get capabilities() {
        return state.capabilities;
    },
    get protocolVersion() {
        return state.protocolVersion;
    },
    get modVersion() {
        return state.modVersion;
    },
    get lastUpdate() {
        return state.lastUpdate;
    },
    /** Sharing with other devices; null on other devices and with mods before 0.3.0 */
    get sharing() {
        return state.sharing;
    },
    get mode(): LiveMode {
        return session.mode;
    },
    /** The game this device pairs with, in paired mode */
    get pairing(): PairingLink | null {
        return session.pairing;
    },
    /** When this device started waiting for the game; null while connected or off */
    get waitingSince(): number | null {
        return timing.waitingSince;
    },
    /** When sharing last had no viewer; null while a device is connected or sharing is off */
    get sharingIdleSince(): number | null {
        return timing.sharingIdleSince;
    },

    /** Player entity (null if not in entity list) */
    get player(): EntityData | null {
        return state.entities.find((e) => e.entityType === 'player') ?? null;
    },

    /** Check if a capability is enabled */
    hasCapability(capability: string): boolean {
        return state.capabilities.includes(capability);
    }
};

/**
 * Connection control API. Choices persist on this device.
 */
export const liveConnection = {
    /**
     * Picks up where this device left off. A pairing link in `hash` wins, then a stored
     * pairing, then `localRequested` (the in-game overlay asks for Live) or a stored
     * choice to connect to this PC. Returns the pairing when `hash` carried one.
     */
    restore(hash: string, localRequested: boolean): PairingLink | null {
        if (!browser) return null;

        const linked = parsePairingHash(hash);
        if (linked) {
            writeStorage(PAIRING_KEY, formatPairing(linked));
            startPaired(linked);
            return linked;
        }

        const stored = readStorage(PAIRING_KEY);
        const pairing = stored ? parsePairing(stored) : null;
        if (pairing) {
            startPaired(pairing);
        } else if (localRequested || readStorage(LOCAL_MODE_KEY) === 'true') {
            writeStorage(LOCAL_MODE_KEY, 'true');
            startLocal();
        }
        return null;
    },

    /**
     * Connects to the mod on this PC.
     */
    connectLocal(): void {
        if (!browser) return;
        writeStorage(PAIRING_KEY, null);
        writeStorage(LOCAL_MODE_KEY, 'true');
        startLocal();
    },

    /**
     * Stops showing live data and forgets the game this device paired with.
     */
    disconnect(): void {
        if (!browser) return;
        writeStorage(PAIRING_KEY, null);
        writeStorage(LOCAL_MODE_KEY, 'false');
        stop();
    },

    /**
     * Asks the mod to start or stop sharing with other devices. The mod answers with
     * sharingChanged. Returns false when not connected.
     */
    setSharing(enabled: boolean): boolean {
        if (!browser) return false;
        return getConnection().send({ type: 'setSharing', enabled });
    },

    /** Check if currently connected */
    get isConnected(): boolean {
        return state.connectionState === 'connected';
    },

    /** Check if connection is enabled (may be connecting/reconnecting) */
    get isEnabled(): boolean {
        return connection?.isEnabled ?? false;
    }
};

/**
 * Svelte 5 reactive state for live entity data from InteractiveMapCompanion mod.
 *
 * Uses runes ($state) for reactive state management.
 * Singleton pattern - all components share the same connection.
 */

import { browser } from '$app/environment';
import { LiveConnection } from './connection';
import type { LiveState, EntityData, ProtocolMessage } from './types';

const INITIAL_STATE: LiveState = {
    connectionState: 'disconnected',
    zone: null,
    entities: [],
    capabilities: [],
    protocolVersion: null,
    modVersion: null,
    lastUpdate: null
};

// Module-level reactive state using $state rune
const state = $state<LiveState>({ ...INITIAL_STATE });

// Singleton connection instance
let connection: LiveConnection | null = null;

function getConnection(): LiveConnection {
    if (!connection) {
        connection = new LiveConnection(
            (connectionState) => {
                state.connectionState = connectionState;

                // Clear entities when disconnected or reconnecting
                if (connectionState === 'disconnected' || connectionState === 'reconnecting') {
                    state.entities = [];
                }
            },
            (message) => {
                handleMessage(message);
            }
        );
    }
    return connection;
}

function handleMessage(message: ProtocolMessage): void {
    switch (message.type) {
        case 'handshake':
            state.zone = message.zone;
            state.capabilities = message.capabilities;
            state.protocolVersion = message.protocolVersion;
            state.modVersion = message.modVersion;
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
 * Connection control API.
 */
export const liveConnection = {
    /**
     * Start connection to mod's WebSocket server.
     * Will automatically reconnect on disconnect until disconnect() is called.
     */
    connect(): void {
        if (!browser) return;
        getConnection().connect();
    },

    /**
     * Stop connection and disable auto-reconnect.
     * Clears all entity data.
     */
    disconnect(): void {
        if (!browser) return;
        getConnection().disconnect();
        // Reset to initial state
        state.connectionState = INITIAL_STATE.connectionState;
        state.zone = INITIAL_STATE.zone;
        state.entities = INITIAL_STATE.entities;
        state.capabilities = INITIAL_STATE.capabilities;
        state.protocolVersion = INITIAL_STATE.protocolVersion;
        state.modVersion = INITIAL_STATE.modVersion;
        state.lastUpdate = INITIAL_STATE.lastUpdate;
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

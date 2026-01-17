/**
 * Protocol types for InteractiveMapCompanion WebSocket communication.
 *
 * These types match the C# protocol defined in the mod. The mod uses
 * System.Text.Json with camelCase naming, so all properties are camelCase.
 */

/**
 * Connection state machine states.
 */
export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

/**
 * Entity type classification.
 * Matches C# EntityType enum values (serialized as snake_case strings).
 */
export type EntityType = 'player' | 'simplayer' | 'pet' | 'npc_friendly' | 'npc_enemy';

/**
 * Entity rarity classification.
 * Matches C# EntityRarity enum values.
 */
export type EntityRarity = 'common' | 'rare' | 'boss';

/**
 * Entity data from stateUpdate messages.
 * Represents a tracked entity's current state.
 */
export interface EntityData {
    /** Unique instance ID within the session */
    id: number;
    /** Classification of the entity */
    entityType: EntityType;
    /** Display name */
    name: string;
    /** Zone-local coordinates [x, y, z] */
    position: [number, number, number];
    /** Facing direction in degrees (0-360, where 0° = north in game coordinates) */
    rotation: number;
    /** Entity level (for NPCs) */
    level?: number;
    /** Rarity classification (for enemies) */
    rarity?: EntityRarity;
}

/**
 * Handshake message sent immediately upon WebSocket connection.
 */
export interface HandshakeMessage {
    type: 'handshake';
    /** Protocol version (semver) */
    protocolVersion: string;
    /** Mod version (semver) */
    modVersion: string;
    /** Current zone/scene name */
    zone: string;
    /** Enabled capabilities for feature detection */
    capabilities: string[];
}

/**
 * Periodic state update containing all tracked entities.
 */
export interface StateUpdateMessage {
    type: 'stateUpdate';
    /** Current zone/scene name */
    zone: string;
    /** Unix timestamp in milliseconds */
    timestamp: number;
    /** All tracked entities */
    entities: EntityData[];
}

/**
 * Notification when player changes zones.
 * Clients should clear entities from the previous zone.
 */
export interface ZoneChangeMessage {
    type: 'zoneChange';
    /** Previous zone name */
    previousZone: string;
    /** New zone name */
    zone: string;
    /** Unix timestamp in milliseconds */
    timestamp: number;
}

/**
 * Union of all protocol message types.
 */
export type ProtocolMessage = HandshakeMessage | StateUpdateMessage | ZoneChangeMessage;

/**
 * Live state exposed to UI components.
 */
export interface LiveState {
    /** Current connection state */
    connectionState: ConnectionState;
    /** Current zone (null if not connected) */
    zone: string | null;
    /** Tracked entities in current zone */
    entities: EntityData[];
    /** Enabled capabilities from handshake */
    capabilities: string[];
    /** Protocol version from handshake */
    protocolVersion: string | null;
    /** Mod version from handshake */
    modVersion: string | null;
    /** Timestamp of last state update */
    lastUpdate: number | null;
}

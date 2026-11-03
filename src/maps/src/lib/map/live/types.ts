/**
 * Protocol types for InteractiveMapCompanion communication.
 *
 * These types match the C# protocol in the mod's `Protocol/Messages.cs`. The mod
 * serializes camelCase JSON and omits null fields.
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
    /** Entity level */
    level?: number;
    /** Rarity classification (for enemies) */
    rarity?: EntityRarity;
    /** Character class display name (for players and SimPlayers) */
    characterClass?: string;
    /** Owner name (for pets) */
    owner?: string;
}

/**
 * Sharing with other devices on the game PC's network. Only the map on the game PC
 * receives it, and only from mods with protocol 0.3.0 or later.
 */
export interface SharingStatus {
    enabled: boolean;
    /** Devices showing the live map now */
    viewers: number;
    /** UDP and TCP port other devices connect to */
    port: number;
    /** Address and port to type on another device, absent when the PC has none */
    address?: string;
    /** Pairing link for the QR code, absent with address */
    link?: string;
    /** Why sharing could not start */
    error?: 'portUnavailable';
}

/**
 * Handshake message sent immediately upon connection.
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
    /** Sharing state, for the map on the game PC only */
    sharing?: SharingStatus;
}

/**
 * Sent to the map on the game PC when sharing starts, stops or fails, and when a
 * device connects or leaves.
 */
export interface SharingChangedMessage {
    type: 'sharingChanged';
    sharing: SharingStatus;
}

/**
 * Sent by the map on the game PC to turn sharing on or off.
 */
export interface SetSharingMessage {
    type: 'setSharing';
    enabled: boolean;
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
 * Union of all messages the mod sends.
 */
export type ProtocolMessage =
    | HandshakeMessage
    | StateUpdateMessage
    | ZoneChangeMessage
    | SharingChangedMessage;

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
    /** Sharing state from the mod, null on other devices and with mods before 0.3.0 */
    sharing: SharingStatus | null;
}

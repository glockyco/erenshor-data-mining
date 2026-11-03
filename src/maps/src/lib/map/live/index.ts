/**
 * Live entity tracking module for InteractiveMapCompanion mod integration.
 *
 * Usage:
 * ```svelte
 * <script lang="ts">
 *     import { liveConnection, liveState } from '$lib/map/live';
 *
 *     onMount(() => liveConnection.restore(location.hash, false));
 * </script>
 *
 * <button onclick={() => liveConnection.connectLocal()}>Connect</button>
 *
 * {#if liveState.connectionState === 'connected' && liveState.player}
 *     Player: {liveState.player.name} at {liveState.player.position.join(', ')}
 * {/if}
 * ```
 */

// Connection control and state
export { liveConnection, liveState, type LiveMode } from './stores.svelte';
export type { PairingLink } from './pairing';

// Types
export type {
    ConnectionState,
    EntityData,
    EntityType,
    EntityRarity,
    LiveState,
    HandshakeMessage,
    StateUpdateMessage,
    ZoneChangeMessage,
    SharingStatus,
    SharingChangedMessage,
    SetSharingMessage,
    ProtocolMessage
} from './types';

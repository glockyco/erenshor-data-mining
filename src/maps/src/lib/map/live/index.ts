/**
 * Live entity tracking module for InteractiveMapCompanion mod integration.
 *
 * Usage:
 * ```svelte
 * <script lang="ts">
 *     import { liveConnection, liveState } from '$lib/map/live';
 *
 *     let liveEnabled = $state(false);
 *
 *     $effect(() => {
 *         if (liveEnabled) {
 *             liveConnection.connect();
 *         } else {
 *             liveConnection.disconnect();
 *         }
 *     });
 * </script>
 *
 * <label>
 *     <input type="checkbox" bind:checked={liveEnabled} />
 *     Live Mode
 * </label>
 *
 * {#if liveState.connectionState === 'connected' && liveState.player}
 *     Player: {liveState.player.name} at {liveState.player.position.join(', ')}
 * {/if}
 * ```
 */

// Connection control and state
export { liveConnection, liveState } from './stores.svelte';

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
    ProtocolMessage
} from './types';

<script lang="ts">
    import type {
        AnyWorldMarker,
        WorldEnemy,
        WorldNpc,
        WorldZoneLine,
        WorldMiningNode,
        WorldWater
    } from '$lib/types/world-map';
    import PopupContainer from './PopupContainer.svelte';
    import EnemyPopupContent from './popups/EnemyPopupContent.svelte';
    import NpcPopupContent from './popups/NpcPopupContent.svelte';
    import ZoneLinePopupContent from './popups/ZoneLinePopupContent.svelte';
    import MiningNodePopupContent from './popups/MiningNodePopupContent.svelte';
    import WaterPopupContent from './popups/WaterPopupContent.svelte';
    import SimplePopupContent from './popups/SimplePopupContent.svelte';

    interface Props {
        marker: AnyWorldMarker;
        zoneName: string;
        onClose: () => void;
        onFocus: () => void;
    }

    let { marker, zoneName, onClose, onFocus }: Props = $props();

    // Get display title based on marker type
    function getTitle(): string {
        switch (marker.category) {
            case 'enemy':
                return 'Spawn Point';
            case 'npc':
                return (marker as WorldNpc).name;
            case 'zone-line':
                return 'Zone Connection';
            case 'mining-node':
                return 'Mining Node';
            case 'water':
                return 'Fishing Spot';
            case 'forge':
                return 'Forge';
            case 'wishing-well':
                return 'Wishing Well';
            case 'door':
                return 'Locked Door';
            case 'item-bag':
                return 'Item Bag';
            case 'teleport':
                return 'Teleport Point';
            case 'secret-passage':
                return 'Secret Passage';
            case 'treasure-loc':
                return 'Treasure Location';
            case 'achievement-trigger':
                return 'Achievement';
            default:
                return 'Unknown';
        }
    }

    // Get category display name (matches sidebar sections)
    function getCategoryLabel(): string {
        switch (marker.category) {
            case 'enemy': {
                const m = marker as WorldEnemy;
                const uniques = m.characters.filter((c) => c.isUnique).length;
                const rares = m.characters.filter((c) => c.isRare && !c.isUnique).length;
                const commons = m.characters.filter((c) => !c.isRare && !c.isUnique).length;
                const parts: string[] = [];
                if (uniques > 0) parts.push(`${uniques} unique`);
                if (rares > 0) parts.push(`${rares} rare`);
                if (commons > 0) parts.push(`${commons} common`);
                return parts.length > 0 ? parts.join(', ') : 'Empty';
            }
            case 'npc':
                return 'NPC';
            case 'zone-line':
            case 'teleport':
                return 'Travel';
            case 'mining-node':
            case 'water':
            case 'item-bag':
            case 'treasure-loc':
                return 'Resource';
            case 'forge':
            case 'wishing-well':
            case 'door':
                return 'Interactable';
            case 'secret-passage':
            case 'achievement-trigger':
                return 'Secret';
            default:
                return '';
        }
    }

    // Get border color based on marker category
    function getBorderColorClass(): string {
        switch (marker.category) {
            case 'enemy': {
                const m = marker as WorldEnemy;
                if (m.isUnique) return 'border-l-white';
                if (m.isRare) return 'border-l-red-500';
                return 'border-l-blue-500';
            }
            case 'npc':
                return 'border-l-green-500';
            case 'zone-line':
                return 'border-l-purple-500';
            case 'door':
                return 'border-l-amber-700';
            case 'item-bag':
                return 'border-l-orange-500';
            case 'mining-node':
                return 'border-l-gray-500';
            case 'teleport':
                return 'border-l-violet-500';
            case 'secret-passage':
                return 'border-l-violet-400';
            case 'achievement-trigger':
                return 'border-l-pink-500';
            case 'forge':
                return 'border-l-orange-600';
            case 'wishing-well':
                return 'border-l-cyan-500';
            case 'treasure-loc':
                return 'border-l-yellow-500';
            case 'water':
                return 'border-l-sky-400';
            default:
                return 'border-l-gray-500';
        }
    }

    const title = $derived(getTitle());
    const categoryLabel = $derived(getCategoryLabel());
    const borderColorClass = $derived(getBorderColorClass());
</script>

<PopupContainer {title} subtitle={categoryLabel} {borderColorClass} {onClose} {onFocus}>
    {#if marker.category === 'enemy'}
        {#key marker.coordinateId}
            <EnemyPopupContent marker={marker as WorldEnemy} />
        {/key}
    {:else if marker.category === 'npc'}
        {#key marker.coordinateId}
            <NpcPopupContent marker={marker as WorldNpc} />
        {/key}
    {:else if marker.category === 'zone-line'}
        <ZoneLinePopupContent marker={marker as WorldZoneLine} />
    {:else if marker.category === 'mining-node'}
        <MiningNodePopupContent marker={marker as WorldMiningNode} />
    {:else if marker.category === 'water'}
        <WaterPopupContent marker={marker as WorldWater} />
    {:else}
        <SimplePopupContent {marker} />
    {/if}
    {#snippet footer()}
        {zoneName}
    {/snippet}
</PopupContainer>

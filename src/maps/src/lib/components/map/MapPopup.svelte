<script lang="ts">
    import type {
        WorldEnemy,
        WorldNpc,
        WorldZoneLine,
        WorldMiningNode,
        WorldWater
    } from '$lib/types/world-map';
    import type { Selection } from '$lib/types/selection';
    import { getSelectionBorderColor } from '$lib/types/selection';
    import PopupContainer from './PopupContainer.svelte';
    import EnemyPopupContent from './popups/EnemyPopupContent.svelte';
    import NpcPopupContent from './popups/NpcPopupContent.svelte';
    import ZoneLinePopupContent from './popups/ZoneLinePopupContent.svelte';
    import MiningNodePopupContent from './popups/MiningNodePopupContent.svelte';
    import WaterPopupContent from './popups/WaterPopupContent.svelte';
    import SimplePopupContent from './popups/SimplePopupContent.svelte';
    import ZonePopup from './ZonePopup.svelte';
    import LivePlayerPopupContent from './popups/LivePlayerPopupContent.svelte';
    import LiveSimPlayerPopupContent from './popups/LiveSimPlayerPopupContent.svelte';
    import LivePetPopupContent from './popups/LivePetPopupContent.svelte';
    import LiveNpcPopupContent from './popups/LiveNpcPopupContent.svelte';

    interface Props {
        selection: Selection;
        zoneName: string;
        onClose: () => void;
        onFocus: () => void;
    }

    let { selection, zoneName, onClose, onFocus }: Props = $props();

    // Get display title based on selection type
    function getTitle(): string {
        if (!selection) return '';

        if (selection.type === 'live') {
            return selection.entity.name;
        }

        if (selection.type === 'zone') {
            return selection.zone.name;
        }

        const marker = selection.marker;
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

    // Get category display name (subtitle)
    function getCategoryLabel(): string {
        if (!selection) return '';

        if (selection.type === 'live') {
            const entity = selection.entity;
            const level = entity.level ? `Level ${entity.level}` : '';

            switch (entity.entityType) {
                case 'player':
                    return ['Player', level].filter(Boolean).join(' • ');
                case 'simplayer':
                    return ['SimPlayer', level].filter(Boolean).join(' • ');
                case 'pet':
                    return ['Pet', level].filter(Boolean).join(' • ');
                case 'npc_friendly':
                    return ['Friendly NPC', level].filter(Boolean).join(' • ');
                case 'npc_enemy': {
                    const parts = ['Enemy', level];
                    if (entity.rarity && entity.rarity !== 'common') {
                        parts.push(entity.rarity.charAt(0).toUpperCase() + entity.rarity.slice(1));
                    }
                    return parts.filter(Boolean).join(' • ');
                }
                default:
                    return 'Live Entity';
            }
        }

        if (selection.type === 'zone') {
            return 'Zone';
        }

        const marker = selection.marker;
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

    // Get border color based on selection type
    function getBorderColorClass(): string {
        if (!selection) return 'border-l-gray-500';
        return getSelectionBorderColor(selection);
    }

    const title = $derived(getTitle());
    const categoryLabel = $derived(getCategoryLabel());
    const borderColorClass = $derived(getBorderColorClass());
</script>

{#if !selection}
    <!-- Nothing -->
{:else if selection.type === 'zone'}
    <ZonePopup zone={selection.zone} {onClose} {onFocus} />
{:else if selection.type === 'live'}
    <PopupContainer {title} subtitle={categoryLabel} {borderColorClass} {onClose} {onFocus}>
        {#if selection.entity.entityType === 'player'}
            <LivePlayerPopupContent entity={selection.entity} />
        {:else if selection.entity.entityType === 'simplayer'}
            <LiveSimPlayerPopupContent entity={selection.entity} />
        {:else if selection.entity.entityType === 'pet'}
            <LivePetPopupContent entity={selection.entity} />
        {:else}
            <LiveNpcPopupContent entity={selection.entity} />
        {/if}
        {#snippet footer()}
            {zoneName}
        {/snippet}
    </PopupContainer>
{:else}
    {@const marker = selection.marker}
    <PopupContainer {title} subtitle={categoryLabel} {borderColorClass} {onClose} {onFocus}>
        {#if marker.category === 'enemy'}
            {#key marker.coordinateId}
                <EnemyPopupContent {marker} />
            {/key}
        {:else if marker.category === 'npc'}
            {#key marker.coordinateId}
                <NpcPopupContent {marker} />
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
{/if}

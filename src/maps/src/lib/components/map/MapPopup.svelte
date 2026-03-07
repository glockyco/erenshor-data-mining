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
    import type { SearchIndex } from '$lib/map/search';
    import PopupContainer from './PopupContainer.svelte';
    import SpawnPointPopupContent from './popups/SpawnPointPopupContent.svelte';
    import ZoneLinePopupContent from './popups/ZoneLinePopupContent.svelte';
    import MiningNodePopupContent from './popups/MiningNodePopupContent.svelte';
    import WaterPopupContent from './popups/WaterPopupContent.svelte';
    import SimplePopupContent from './popups/SimplePopupContent.svelte';
    import ZonePopup from './ZonePopup.svelte';
    import LivePlayerPopupContent from './popups/LivePlayerPopupContent.svelte';
    import LiveSimPlayerPopupContent from './popups/LiveSimPlayerPopupContent.svelte';
    import LivePetPopupContent from './popups/LivePetPopupContent.svelte';
    import LiveNpcPopupContent from './popups/LiveNpcPopupContent.svelte';
    import SearchEnemyPopup from './popups/SearchEnemyPopup.svelte';
    import SearchNpcPopup from './popups/SearchNpcPopup.svelte';
    import SearchNotFoundContent from './popups/SearchNotFoundContent.svelte';

    interface Props {
        selection: Selection;
        zoneName: string;
        searchIndex: SearchIndex | null;
        mode?: 'panel' | 'drawer';
        onClose: () => void;
        onFocus: () => void;
        onHoverSpawn: (stableKey: string | null) => void;
        onFocusSpawn: (stableKey: string) => void;
        onFocusAll: () => void;
        onSearchAlternative: (query: string) => void;
    }

    let {
        selection,
        zoneName,
        searchIndex,
        mode = 'panel',
        onClose,
        onFocus,
        onHoverSpawn,
        onFocusSpawn,
        onFocusAll,
        onSearchAlternative
    }: Props = $props();

    // Get display title based on selection type
    function getTitle(): string {
        if (!selection) return '';

        if (selection.type === 'live') {
            return selection.entity.name;
        }

        if (selection.type === 'zone') {
            return selection.zone.name;
        }

        if (selection.type === 'search-not-found') {
            return selection.name;
        }

        if (selection.type === 'search') {
            const r = selection.result;
            switch (r.type) {
                case 'enemy':
                    return r.name;
                case 'npc':
                    return r.name;
                case 'zone':
                    return r.name;
            }
        }

        const marker = selection.marker;
        switch (marker.category) {
            case 'enemy':
            case 'npc':
                return 'Spawn Point';
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
                    return ['Player', level].filter(Boolean).join(' \u2022 ');
                case 'simplayer':
                    return ['SimPlayer', level].filter(Boolean).join(' \u2022 ');
                case 'pet':
                    return ['Pet', level].filter(Boolean).join(' \u2022 ');
                case 'npc_friendly':
                    return ['Friendly NPC', level].filter(Boolean).join(' \u2022 ');
                case 'npc_enemy': {
                    const parts = ['Enemy', level];
                    if (entity.rarity && entity.rarity !== 'common') {
                        parts.push(entity.rarity.charAt(0).toUpperCase() + entity.rarity.slice(1));
                    }
                    return parts.filter(Boolean).join(' \u2022 ');
                }
                default:
                    return 'Live Entity';
            }
        }

        if (selection.type === 'zone') {
            return 'Zone';
        }

        if (selection.type === 'search-not-found') {
            return 'Not Found';
        }

        if (selection.type === 'search') {
            const r = selection.result;
            switch (r.type) {
                case 'enemy': {
                    const parts: string[] = ['Enemy'];
                    if (r.isUnique) parts.push('Unique');
                    else if (r.isRare) parts.push('Rare');
                    parts.push(`${r.spawnCount} spawn${r.spawnCount !== 1 ? 's' : ''}`);
                    parts.push(`${r.zoneCount} zone${r.zoneCount !== 1 ? 's' : ''}`);
                    return parts.join(' \u2022 ');
                }
                case 'npc': {
                    const parts: string[] = ['NPC'];
                    if (r.isVendor) parts.push('Vendor');
                    parts.push(`${r.spawnCount} location${r.spawnCount !== 1 ? 's' : ''}`);
                    parts.push(`${r.zoneCount} zone${r.zoneCount !== 1 ? 's' : ''}`);
                    return parts.join(' \u2022 ');
                }
                case 'zone':
                    return 'Zone';
            }
        }

        const marker = selection.marker;
        switch (marker.category) {
            case 'enemy':
            case 'npc': {
                const m = marker as WorldEnemy | WorldNpc;
                const uniques = m.characters.filter((c) => c.isUnique).length;
                const rares = m.characters.filter((c) => c.isRare && !c.isUnique).length;
                const commons = m.characters.filter((c) => !c.isRare && !c.isUnique).length;
                const parts: string[] = [];
                if (uniques > 0) parts.push(`${uniques} unique`);
                if (rares > 0) parts.push(`${rares} rare`);
                if (commons > 0) parts.push(`${commons} common`);
                return parts.length > 0 ? parts.join(', ') : 'Empty';
            }
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

    function getBorderColorClass(): string {
        if (!selection) return 'border-l-gray-500';
        return getSelectionBorderColor(selection);
    }

    const title = $derived(getTitle());
    const categoryLabel = $derived(getCategoryLabel());
    const borderColorClass = $derived(getBorderColorClass());

    // Get search result markers for popups
    const searchEnemyMarkers = $derived.by(() => {
        if (selection?.type !== 'search' || selection.result.type !== 'enemy' || !searchIndex)
            return [];
        return searchIndex.enemyProvider.getMarkers(selection.result.name);
    });

    const searchNpcMarkers = $derived.by(() => {
        if (selection?.type !== 'search' || selection.result.type !== 'npc' || !searchIndex)
            return [];
        return searchIndex.npcProvider.getMarkers(selection.result.name);
    });
</script>

{#if !selection}
    <!-- Nothing -->
{:else if selection.type === 'zone'}
    <ZonePopup zone={selection.zone} {mode} {onClose} {onFocus} />
{:else if selection.type === 'search'}
    {@const result = selection.result}
    <PopupContainer
        {title}
        subtitle={categoryLabel}
        {borderColorClass}
        showFocus={false}
        {mode}
        {onClose}
        {onFocus}
    >
        {#if result.type === 'enemy'}
            <SearchEnemyPopup
                name={result.name}
                markers={searchEnemyMarkers}
                {onHoverSpawn}
                {onFocusSpawn}
                {onFocusAll}
            />
        {:else if result.type === 'npc'}
            <SearchNpcPopup
                name={result.name}
                markers={searchNpcMarkers}
                {onHoverSpawn}
                {onFocusSpawn}
                {onFocusAll}
            />
        {/if}
    </PopupContainer>
{:else if selection.type === 'search-not-found'}
    <PopupContainer
        {title}
        subtitle={categoryLabel}
        {borderColorClass}
        showFocus={false}
        {mode}
        {onClose}
        {onFocus}
    >
        <SearchNotFoundContent
            searchType={selection.searchType}
            name={selection.name}
            {onSearchAlternative}
        />
    </PopupContainer>
{:else if selection.type === 'live'}
    <PopupContainer {title} subtitle={categoryLabel} {borderColorClass} {mode} {onClose} {onFocus}>
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
    <PopupContainer {title} subtitle={categoryLabel} {borderColorClass} {mode} {onClose} {onFocus}>
        {#if marker.category === 'enemy' || marker.category === 'npc'}
            {#key marker.stableKey}
                <SpawnPointPopupContent marker={marker as WorldEnemy | WorldNpc} />
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

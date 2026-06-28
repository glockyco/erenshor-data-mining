<script lang="ts">
    import { Command } from 'bits-ui';
    import { searchMarkers, type SearchResult, type SearchMatch, type IndexEntry } from '$lib/map/search';
    import { splitByMatchRange, type TextSegment } from '$lib/map/search/match-highlight';
    import { Rarity } from '$lib/map-markers';
    import type { EntityData } from '$lib/map/live/types';
    import * as Drawer from '$lib/components/ui/drawer';
    import Skull from '@lucide/svelte/icons/skull';
    import User from '@lucide/svelte/icons/user';
    import MapIcon from '@lucide/svelte/icons/map';
    import Radio from '@lucide/svelte/icons/radio';
    import Package from '@lucide/svelte/icons/package';
    import SearchChips from './SearchChips.svelte';
    import { computeChipCounts, type Category } from './search-chips';

    // Live-only result type, separate from the static SearchResult union
    type LiveSearchResult = { kind: 'live'; entity: EntityData; zone: string; matchRange: [number, number] | null };

    // Combined item for the rendered list
    type AnyResult = { kind: 'static'; match: SearchMatch } | LiveSearchResult;

    interface Props {
        open: boolean;
        isDesktop: boolean;
        initialQuery?: string;
        index: IndexEntry[];
        liveEntities: EntityData[];
        liveZone: string | null;
        onselect: (result: SearchResult) => void;
        onliveselect: (entity: EntityData, zone: string) => void;
        onclose: () => void;
    }

    let {
        open = $bindable(),
        isDesktop,
        initialQuery = $bindable(''),
        index,
        liveEntities,
        liveZone,
        onselect,
        onliveselect,
        onclose
    }: Props = $props();

    let query = $state('');
    let staticResults = $state<SearchMatch[]>([]);
    let liveResults = $state<LiveSearchResult[]>([]);
    let loading = $state(false);
    let activeCategory = $state<Category>('all');

    // Debounced search
    let searchTimeout: ReturnType<typeof setTimeout>;
    $effect(() => {
        clearTimeout(searchTimeout);
        if (query.length >= 2) {
            loading = true;
            searchTimeout = setTimeout(() => {
                staticResults = searchMarkers(query, index);
                liveResults = searchLiveEntities(query);
                loading = false;
            }, 150);
        } else {
            staticResults = [];
            liveResults = [];
            loading = false;
        }
    });

    // Seed query from initialQuery when opening, reset when closing
    $effect(() => {
        if (open) {
            if (initialQuery) {
                query = initialQuery;
                initialQuery = '';
            }
        } else {
            query = '';
            staticResults = [];
            liveResults = [];
        }
    });

    /**
     * Search live entities by name. Prefix matches first, then substring.
     * Capped at 5 results — live entities are transient and highly contextual.
     */
    function searchLiveEntities(q: string): LiveSearchResult[] {
        if (!liveZone || liveEntities.length === 0) return [];
        const lower = q.toLowerCase().trim();
        const zone = liveZone;
        const prefix: LiveSearchResult[] = [];
        const substring: LiveSearchResult[] = [];
        for (const entity of liveEntities) {
            const nameLower = entity.name.toLowerCase();
            const startIdx = nameLower.indexOf(lower);
            if (startIdx === 0) {
                prefix.push({ kind: 'live', entity, zone, matchRange: [0, lower.length] });
            } else if (startIdx > 0) {
                substring.push({ kind: 'live', entity, zone, matchRange: [startIdx, startIdx + lower.length] });
            }
        }
        return [...prefix, ...substring].slice(0, 5);
    }

    function handleSelect(item: AnyResult) {
        if (item.kind === 'live') {
            onliveselect(item.entity, item.zone);
        } else {
            onselect(item.match.result);
        }
        open = false;
    }

    // Category display config for static results
    const categoryLabels: Record<SearchResult['type'], string> = {
        enemy: 'Enemy Spawn Points',
        npc: 'NPC Spawn Points',
        zone: 'Zones',
        item: 'Drops'
    };

    // staticCategoryOrder controls display grouping in MapSearch.svelte;
    // categoryOrder (in index.ts) controls interleaving priority within
    // buildSearchIndex. Both set items first.
    const staticCategoryOrder: SearchResult['type'][] = ['item', 'enemy', 'npc', 'zone'];

    function groupStaticByCategory(
        items: SearchMatch[]
    ): [SearchResult['type'], SearchMatch[]][] {
        const groups: Partial<Record<SearchResult['type'], SearchMatch[]>> = {};
        for (const item of items) {
            (groups[item.result.type] ??= []).push(item);
        }
        return staticCategoryOrder.filter((cat) => groups[cat]).map((cat) => [cat, groups[cat]!]);
    }

    function getStaticResultSublabel(result: SearchResult): string {
        switch (result.type) {
            case 'enemy': {
                const parts: string[] = [];
                if (result.effectiveRarity === Rarity.unique) parts.push('Unique');
                else if (result.effectiveRarity === Rarity.rare) parts.push('Rare');
                parts.push(`${result.spawnCount} spawn${result.spawnCount !== 1 ? 's' : ''}`);
                parts.push(`${result.zoneCount} zone${result.zoneCount !== 1 ? 's' : ''}`);
                return parts.join(' · ');
            }
            case 'npc': {
                const parts: string[] = [];
                if (result.isVendor) parts.push('Vendor');
                parts.push(`${result.spawnCount} spawn${result.spawnCount !== 1 ? 's' : ''}`);
                parts.push(`${result.zoneCount} zone${result.zoneCount !== 1 ? 's' : ''}`);
                return parts.join(' · ');
            }
            case 'zone':
                return 'Zone';
            case 'item':
                return `${result.dropperCount} dropper${result.dropperCount !== 1 ? 's' : ''} · ${result.zoneCount} zone${result.zoneCount !== 1 ? 's' : ''}`;
        }
    }

    function getStaticResultValue(result: SearchResult): string {
        switch (result.type) {
            case 'enemy':
                return `enemy-${result.name}`;
            case 'npc':
                return `npc-${result.name}`;
            case 'zone':
                return `zone-${result.key}`;
            case 'item':
                return `item-${result.itemStableKey}`;
        }
    }

    /** Split a result name into highlight segments based on the match range. */
    function getResultSegments(match: SearchMatch): TextSegment[] {
        const name = match.result.type === 'item' ? match.result.itemName : match.result.name;
        return splitByMatchRange(name, match.matchRange);
    }

    /** Human-readable label for an entity type. */
    function getLiveEntityTypeLabel(entity: EntityData): string {
        switch (entity.entityType) {
            case 'player':
                return 'Player';
            case 'simplayer':
                return 'SimPlayer';
            case 'pet':
                return 'Pet';
            case 'npc_friendly':
                return 'Friendly NPC';
            case 'npc_enemy':
                return 'Enemy';
        }
    }

    /** Sub-label for a live entity result. */
    function getLiveResultSublabel(entity: EntityData): string {
        const parts: string[] = [getLiveEntityTypeLabel(entity)];
        if (entity.level != null) parts.push(`Lv ${entity.level}`);
        // Rarity only meaningful for npc_enemy
        if (entity.entityType === 'npc_enemy' && entity.rarity) {
            const rarityLabel =
                entity.rarity === 'boss' ? 'Boss' : entity.rarity === 'rare' ? 'Rare' : 'Common';
            parts.push(rarityLabel);
        }
        // Class for player / simplayer
        if (entity.characterClass) parts.push(entity.characterClass);
        // Owner for pets
        if (entity.owner) parts.push(`owned by ${entity.owner}`);
        return parts.join(' · ');
    }

    // Scroll fix for bits-ui Command
    function fixScrollIntoView(node: HTMLElement) {
        function isFullyVisible(el: HTMLElement, container: HTMLElement): boolean {
            const elRect = el.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            return elRect.top >= containerRect.top && elRect.bottom <= containerRect.bottom;
        }

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.attributeName !== 'aria-selected') continue;
                const target = mutation.target as HTMLElement;
                if (target.getAttribute('aria-selected') !== 'true') continue;

                const list = node.querySelector('[data-command-list]');
                if (list && !isFullyVisible(target, list as HTMLElement)) {
                    target.scrollIntoView({ block: 'nearest' });
                }
            }
        });

        observer.observe(node, {
            subtree: true,
            attributes: true,
            attributeFilter: ['aria-selected']
        });

        return { destroy: () => observer.disconnect() };
    }

    // Chip counts from current results
    const chipCounts = $derived(computeChipCounts(staticResults, liveResults.length));

    // Filtered results by active category
    const filteredStatic = $derived(
        activeCategory === 'all' || activeCategory === 'live'
            ? staticResults
            : staticResults.filter((m) => m.result.type === activeCategory)
    );
    const filteredLive = $derived(
        activeCategory === 'all' || activeCategory === 'live' ? liveResults : []
    );
    const filteredHasResults = $derived(filteredStatic.length > 0 || filteredLive.length > 0);

    // Arrow-key category switching when focus is in the chip row
    function handleChipKeydown(e: KeyboardEvent) {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        const order: Category[] = ['all', 'live', 'item', 'enemy', 'npc', 'zone'];
        const available = order.filter(
            (c) => c === 'all' || (chipCounts.get(c) ?? 0) > 0 || c === 'live'
        );
        const currentIdx = available.indexOf(activeCategory);
        e.preventDefault();
        const dir = e.key === 'ArrowRight' ? 1 : -1;
        const nextIdx = (currentIdx + dir + available.length) % available.length;
        activeCategory = available[nextIdx];
    }
</script>

{#snippet searchContent()}
    <div class="flex items-center border-b border-zinc-700 px-3">
        <svg
            class="mr-2 h-4 w-4 shrink-0 text-zinc-500"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
        >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <Command.Input
            bind:value={query}
            autofocus
            placeholder="Search enemies, NPCs, zones..."
            class="flex h-12 w-full bg-transparent text-sm text-white placeholder:text-zinc-500
                   outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
    </div>
    {#if query.length >= 2 && (staticResults.length > 0 || liveResults.length > 0)}
        <div role="toolbar" aria-label="Filter results by category" tabindex="0" onkeydown={handleChipKeydown}>
            <SearchChips
                activeCategory={activeCategory}
                counts={chipCounts}
                onSelect={(cat) => (activeCategory = cat)}
            />
        </div>
    {/if}
    <div use:fixScrollIntoView>
        <Command.List class="max-h-80 overflow-y-auto px-2 py-2">
            {#if loading}
                <Command.Loading>
                    <div class="py-6 text-center text-sm text-zinc-500">Searching...</div>
                </Command.Loading>
            {:else if query.length < 2}
                <Command.Empty>
                    <div class="py-6 text-center text-sm text-zinc-500">
                        Type at least 2 characters to search
                    </div>
                </Command.Empty>
            {:else if !filteredHasResults}
                <Command.Empty>
                    <div class="py-6 text-center text-sm text-zinc-500">
                        No results found for "{query}"
                    </div>
                </Command.Empty>
            {:else}
                <!-- Live entities first -->
                {#if filteredLive.length > 0}
                    <Command.Group>
                        <Command.GroupHeading
                            class="px-2 py-1.5 text-xs font-semibold text-zinc-500 uppercase tracking-wide"
                        >
                            Live Entities
                        </Command.GroupHeading>
                        <Command.GroupItems>
                            {#each filteredLive as item (item.entity.id)}
                                <Command.Item
                                    value={`live-${item.entity.id}`}
                                    onSelect={() => handleSelect(item)}
                                    class="flex items-center gap-3 rounded-lg px-2 py-2
                                           text-sm text-zinc-300 cursor-pointer
                                           aria-selected:bg-zinc-700 aria-selected:text-white"
                                >
                                    <Radio class="h-4 w-4 shrink-0 text-lime-400" />
                                    <div class="min-w-0 flex-1">
                                        <div class="truncate">
                                            {#each splitByMatchRange(item.entity.name, item.matchRange) as seg, i (i)}
                                                {#if seg.highlighted}
                                                    <mark class="rounded bg-accent/20 px-0.5 text-white font-semibold">{seg.text}</mark>
                                                {:else}
                                                    {seg.text}
                                                {/if}
                                            {/each}
                                        </div>
                                        <div class="text-xs text-zinc-500 truncate">
                                            {getLiveResultSublabel(item.entity)}
                                        </div>
                                    </div>
                                </Command.Item>
                            {/each}
                        </Command.GroupItems>
                    </Command.Group>
                {/if}

                <!-- Static results grouped by category -->
                {#each groupStaticByCategory(filteredStatic) as [category, items] (category)}
                    <Command.Group>
                        <Command.GroupHeading
                            class="px-2 py-1.5 text-xs font-semibold text-zinc-500 uppercase tracking-wide"
                        >
                            {categoryLabels[category]}
                        </Command.GroupHeading>
                        <Command.GroupItems>
                            {#each items as match (getStaticResultValue(match.result))}
                                {@const result = match.result}
                                <Command.Item
                                    value={getStaticResultValue(result)}
                                    onSelect={() => handleSelect({ kind: 'static', match })}
                                    class="flex items-center gap-3 rounded-lg px-2 py-2
                                           text-sm text-zinc-300 cursor-pointer
                                           aria-selected:bg-zinc-700 aria-selected:text-white"
                                >
                                    {#if result.type === 'enemy'}
                                        <Skull class="h-4 w-4 shrink-0 text-amber-500" />
                                    {:else if result.type === 'npc'}
                                        <User class="h-4 w-4 shrink-0 text-sky-500" />
                                    {:else if result.type === 'item' && result.iconName}
                                        <img src={`/items/${result.iconName}.w20.webp`} alt="" class="h-5 w-5 shrink-0" />
                                    {:else if result.type === 'item'}
                                        <Package class="h-4 w-4 shrink-0 text-emerald-500" />
                                    {:else}
                                        <MapIcon class="h-4 w-4 shrink-0 text-purple-500" />
                                    {/if}
                                    <div class="min-w-0 flex-1">
                                        <div class="truncate">
                                            {#each getResultSegments(match) as seg, i (i)}
                                                {#if seg.highlighted}
                                                    <mark class="rounded bg-accent/20 px-0.5 text-white font-semibold">{seg.text}</mark>
                                                {:else}
                                                    {seg.text}
                                                {/if}
                                            {/each}
                                            {#if match.matchRange === null}
                                                <span class="ml-1.5 inline-flex items-center rounded bg-zinc-700/60 px-1 py-0.5 text-[10px] font-medium text-zinc-400 align-middle">fuzzy</span>
                                            {/if}
                                        </div>
                                        <div class="text-xs text-zinc-500 truncate">
                                            {getStaticResultSublabel(result)}
                                        </div>
                                    </div>
                                </Command.Item>
                            {/each}
                        </Command.GroupItems>
                    </Command.Group>
                {/each}
            {/if}
        </Command.List>
    </div>
{/snippet}

{#if isDesktop}
    {#if open}
        <!-- Desktop: Backdrop -->
        <button
            type="button"
            class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            aria-label="Close search"
            onclick={() => {
                open = false;
                onclose();
            }}
        ></button>

        <!-- Desktop: Command palette -->
        <div
            class="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2
                   rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl"
        >
            <Command.Root shouldFilter={false}>
                {@render searchContent()}
            </Command.Root>
        </div>
    {/if}
{:else}
    <!-- Mobile: Command palette in bottom drawer -->
    <Drawer.Root bind:open shouldScaleBackground={false}>
        <Drawer.Content>
            <Drawer.Header class="sr-only">
                <Drawer.Title>Search Map</Drawer.Title>
            </Drawer.Header>
            <Command.Root shouldFilter={false} class="bg-transparent">
                {@render searchContent()}
            </Command.Root>
        </Drawer.Content>
    </Drawer.Root>
{/if}

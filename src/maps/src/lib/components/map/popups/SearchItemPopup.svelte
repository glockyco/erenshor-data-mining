<script lang="ts">
    import { SvelteMap } from 'svelte/reactivity';
    import type {
        WorldEnemy,
        WorldNpc,
        WorldMiningNode,
        WorldWater,
        WorldItemBag,
        WorldZoneLine
    } from '$lib/types/world-map';
    import type { AnySourceMarker } from '$lib/map/search/item-source-provider';
    import type { PresentedItemSource } from '$lib/map/search/item-source-presentation';
    import type { ItemSearchResult } from '$lib/map/search';
    import { commonWorldSourceLabel } from '$lib/map/search';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import Crosshair from '@lucide/svelte/icons/crosshair';

    type AnySpawnMarker = WorldEnemy | WorldNpc;
    type Presented<K extends PresentedItemSource['kind']> = Extract<PresentedItemSource, { kind: K }>;

    interface Props {
        result: ItemSearchResult;
        sources: PresentedItemSource[];
        onHoverSpawn: (stableKey: string | string[] | null) => void;
        onFocusSpawn: (stableKey: string | string[]) => void;
        onFocusAll: () => void;
    }

    interface ZoneDropper {
        source: Presented<'drop'>;
        row: Presented<'drop'>['row'];
        spawns: AnySpawnMarker[];
    }

    interface ZoneVendor {
        source: Presented<'vendor'>;
        row: Presented<'vendor'>['row'];
        spawns: AnySpawnMarker[];
    }

    interface ZoneDropperGroup {
        zone: string;
        zoneName: string;
        rows: ZoneDropper[];
    }

    interface ZoneVendorGroup {
        zone: string;
        zoneName: string;
        rows: ZoneVendor[];
    }

    interface MiningEntry {
        marker: WorldMiningNode;
        chances: number[];
    }

    interface FishingEntry {
        marker: WorldWater;
        periods: Set<'day' | 'night' | null>;
        chances: number[];
    }

    /** Places of a zone that need the same conditions. */
    interface ConditionGroup {
        key: string;
        zone: string;
        zoneName: string;
        conditions: string[];
        sourceKeys: Set<string>;
    }

    interface ZoneMiningGroup extends ConditionGroup {
        entries: Map<string, MiningEntry>;
    }

    interface ZoneFishingGroup extends ConditionGroup {
        entries: Map<string, FishingEntry>;
    }

    interface ZoneBagGroup extends ConditionGroup {
        markers: Map<string, WorldItemBag>;
    }

    let { result, sources, onHoverSpawn, onFocusSpawn, onFocusAll }: Props = $props();

    function sourceMarkers(source: PresentedItemSource): AnySourceMarker[] {
        if ('markers' in source) return source.markers;
        if ('marker' in source) return [source.marker];
        return [];
    }

    const allMarkers = $derived.by(() => {
        const markers = new SvelteMap<string, AnySourceMarker>();
        for (const source of sources) {
            for (const marker of sourceMarkers(source)) {
                markers.set(marker.stableKey, marker);
            }
        }
        return [...markers.values()];
    });

    const auctionHouses = $derived(sources.filter((source) => source.kind === 'auction_house'));

    const unlocatedDroppers = $derived(sources.filter(
        (source): source is Presented<'drop'> => source.kind === 'drop' && source.markers.length === 0
    ));
    const unlocatedVendors = $derived(sources.filter(
        (source): source is Presented<'vendor'> => source.kind === 'vendor' && source.markers.length === 0
    ));
    const treasureGroups = $derived.by(() => {
        const groups = new SvelteMap<string, {
            key: string;
            row: Presented<'treasure'>['row'];
            zoneName: string;
            markers: AnySourceMarker[];
            conditions: string[];
            sourceKeys: Set<string>;
        }>();
        for (const source of sources) {
            if (source.kind !== 'treasure') continue;
            for (const marker of source.markers) {
                const key = JSON.stringify([source.row.characterStableKey, marker.zone, source.row.playerLevelMin, source.row.playerLevelMax, source.row.dropProbability, source.conditions]);
                const group = groups.get(key);
                if (group) {
                    group.markers.push(marker);
                    for (const sourceKey of source.sourceKeys) group.sourceKeys.add(sourceKey);
                } else {
                    groups.set(key, { key, row: source.row, zoneName: marker.zoneName, markers: [marker], conditions: source.conditions,
                        sourceKeys: new Set(source.sourceKeys) });
                }
            }
        }
        return [...groups.values()];
    });

    const droppersByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneDropperGroup>();

        for (const source of sources) {
            if (source.kind !== 'drop') continue;
            const byZone = new SvelteMap<string, AnySpawnMarker[]>();
            for (const marker of source.markers) {
                const spawns = byZone.get(marker.zone);
                if (spawns) spawns.push(marker);
                else byZone.set(marker.zone, [marker]);
            }

            for (const [zone, spawns] of byZone) {
                const group = groups.get(zone);
                const row = { source, row: source.row, spawns };
                if (group) group.rows.push(row);
                else {
                    groups.set(zone, {
                        zone,
                        zoneName: spawns[0]?.zoneName ?? zone,
                        rows: [row]
                    });
                }
            }
        }

        return [...groups.values()]
            .sort((a, b) => b.rows.length - a.rows.length)
            .map((group) => ({
                ...group,
                rows: [...group.rows].sort((a, b) => (b.row.dropProbability ?? -1) - (a.row.dropProbability ?? -1))
            }));
    });

    const vendorsByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneVendorGroup>();

        for (const source of sources) {
            if (source.kind !== 'vendor') continue;
            const byZone = new SvelteMap<string, AnySpawnMarker[]>();
            for (const marker of source.markers) {
                const spawns = byZone.get(marker.zone);
                if (spawns) spawns.push(marker);
                else byZone.set(marker.zone, [marker]);
            }

            for (const [zone, spawns] of byZone) {
                const group = groups.get(zone);
                const row = { source, row: source.row, spawns };
                if (group) group.rows.push(row);
                else {
                    groups.set(zone, {
                        zone,
                        zoneName: spawns[0]?.zoneName ?? zone,
                        rows: [row]
                    });
                }
            }
        }

        return [...groups.values()]
            .sort((a, b) => b.rows.length - a.rows.length)
            .map((group) => ({
                ...group,
                rows: [...group.rows].sort((a, b) => a.row.price - b.row.price)
            }));
    });

    /** Groups one marker per source by zone and by the conditions its source needs there. */
    function groupByZone<G extends ConditionGroup>(
        source: PresentedItemSource,
        marker: AnySourceMarker,
        groups: Map<string, G>,
        create: (base: ConditionGroup) => G
    ): G {
        const key = JSON.stringify([marker.zone, source.conditions]);
        let group = groups.get(key);
        if (!group) {
            group = create({ key, zone: marker.zone, zoneName: marker.zoneName, conditions: source.conditions, sourceKeys: new Set() });
            groups.set(key, group);
        }
        for (const sourceKey of source.sourceKeys) group.sourceKeys.add(sourceKey);
        return group;
    }

    const miningByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneMiningGroup>();

        for (const source of sources) {
            if (source.kind !== 'mining') continue;
            const marker = source.marker;
            const group = groupByZone(source, marker, groups, (base) => ({ ...base, entries: new Map() }));
            const entry = group.entries.get(marker.stableKey);
            const chance = source.row.dropChance;
            if (entry) {
                if (chance !== null) entry.chances.push(chance);
            } else {
                group.entries.set(marker.stableKey, {
                    marker,
                    chances: chance === null ? [] : [chance]
                });
            }
        }

        return [...groups.values()].sort((a, b) => b.entries.size - a.entries.size);
    });

    const fishingByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneFishingGroup>();

        for (const source of sources) {
            if (source.kind !== 'fishing') continue;
            const marker = source.marker;
            const group = groupByZone(source, marker, groups, (base) => ({ ...base, entries: new Map() }));
            const entry = group.entries.get(marker.stableKey);
            const chance = source.row.dropChance;
            if (entry) {
                entry.periods.add(source.row.period);
                if (chance !== null) entry.chances.push(chance);
            } else {
                group.entries.set(marker.stableKey, {
                    marker,
                    periods: new Set([source.row.period]),
                    chances: chance === null ? [] : [chance]
                });
            }
        }

        return [...groups.values()].sort((a, b) => b.entries.size - a.entries.size);
    });

    const anyWater = $derived(sources.filter((source) => source.kind === 'any_water'));

    const bagsByZone = $derived.by(() => {
        const groups = new SvelteMap<string, ZoneBagGroup>();

        for (const source of sources) {
            if (source.kind !== 'bag') continue;
            const marker = source.marker;
            const group = groupByZone(source, marker, groups, (base) => ({ ...base, markers: new Map() }));
            group.markers.set(marker.stableKey, marker);
        }

        return [...groups.values()].sort((a, b) => b.markers.size - a.markers.size);
    });

    const giversByZone = $derived.by(() => {
        const groups = new SvelteMap<
            string,
            {
                zone: string;
                zoneName: string;
                rows: {
                    source: Presented<'dialog'>;
                    row: Presented<'dialog'>['row'];
                    spawns: AnySpawnMarker[];
                }[];
            }
        >();
        for (const source of sources) {
            if (source.kind !== 'dialog') continue;
            const byZone = new SvelteMap<string, AnySpawnMarker[]>();
            for (const marker of source.markers) {
                const spawns = byZone.get(marker.zone);
                if (spawns) spawns.push(marker);
                else byZone.set(marker.zone, [marker]);
            }
            for (const [zone, spawns] of byZone) {
                let group = groups.get(zone);
                if (!group) {
                    group = { zone, zoneName: spawns[0].zoneName, rows: [] };
                    groups.set(zone, group);
                }
                group.rows.push({ source, row: source.row, spawns });
            }
        }
        return [...groups.values()].sort((a, b) => a.zoneName.localeCompare(b.zoneName));
    });
    const unlocatedGivers = $derived(sources.filter(
        (source): source is Presented<'dialog'> => source.kind === 'dialog' && source.markers.length === 0
    ));

    const quests = $derived.by(() => {
        const groups = new SvelteMap<
            string,
            {
                row: Presented<'quest'>['row'];
                sourceKeys: Set<string>;
                turnIns: Presented<'quest'>[];
            }
        >();
        for (const source of sources) {
            if (source.kind !== 'quest') continue;
            let group = groups.get(source.row.questStableKey);
            if (!group) {
                group = { row: source.row, sourceKeys: new Set(), turnIns: [] };
                groups.set(source.row.questStableKey, group);
            }
            for (const sourceKey of source.sourceKeys) group.sourceKeys.add(sourceKey);
            group.turnIns.push(source);
        }
        // Conditions that every turn-in needs appear once under the quest.
        return [...groups.values()].map((group) => {
            const shared = group.turnIns[0].conditions.filter((line) => group.turnIns.every((turnIn) => turnIn.conditions.includes(line)));
            return { ...group, shared, turnIns: group.turnIns.map((turnIn) => ({ ...turnIn, conditions: turnIn.conditions.filter((line) => !shared.includes(line)) })) };
        });
    });
    const uiGrants = $derived(sources.filter((source) => source.kind === 'ui_grant'));
    const recipes = $derived(sources.filter((s) => s.kind === 'craft'));
    const itemUses = $derived(sources.filter((s) => s.kind === 'item_use'));
    const starting = $derived(sources.filter((s) => s.kind === 'starting'));
    const commonWorldDrops = $derived(sources.filter((s) => s.kind === 'common_world_item'));

    const worldDrops = $derived(
        sources
            .filter((source) => source.kind === 'world')
            .sort((a, b) => (b.row.dropProbability ?? -1) - (a.row.dropProbability ?? -1))
    );

    // Two significant digits: world drop chances range from 1% down to 0.002%.
    function formatWorldDropChance(pct: number): string {
        return `${Number(pct.toPrecision(2))}%`;
    }

    function focusMarkers(markers: AnySourceMarker[]): void {
        if (markers.length > 0) onFocusSpawn(markerKeys(markers));
    }

    function markerKeys(markers: AnySourceMarker[]): string[] {
        return [...new Set(markers.map((marker) => marker.stableKey))];
    }

    function formatDropChance(pct: number): string {
        // One decimal for sub-percent chances, integer otherwise
        return pct < 1 ? `${pct.toFixed(1)}%` : `${Math.round(pct)}%`;
    }

    function formatChanceRange(chances: number[]): string {
        if (chances.length === 0) return 'unknown';
        const min = Math.min(...chances);
        const max = Math.max(...chances);
        return min === max
            ? formatDropChance(max)
            : `${formatDropChance(min)}–${formatDropChance(max)}`;
    }

    function dropText(pct: number | null): string {
        return pct === null ? 'chance unknown' : `${formatDropChance(pct)} drop`;
    }

    function sourceKeys(keys: Iterable<string>): string {
        return JSON.stringify([...keys]);
    }

    const formatPrice = (n: number): string => n.toLocaleString();

    /** Rows of one character that need different conditions still count as one vendor or dropper. */
    function characterCount(rows: { row: { characterStableKey: string } }[]): number {
        return new Set(rows.map((entry) => entry.row.characterStableKey)).size;
    }

    /** The established sentence, with the level windows of the routes that list the item. */
    function auctionAvailability(levels: Presented<'auction_house'>['row']): string {
        const list = (parts: string[]) => parts.length < 2 ? parts.join('') : `${parts.slice(0, -1).join(', ')} or ${parts[parts.length - 1]}`;
        const simulated = levels.simulatedPlayerLevels.length ? ` of level ${list(levels.simulatedPlayerLevels)}` : '';
        const player = levels.playerLevels.length ? `${simulated ? ', or' : ''} while you are level ${list(levels.playerLevels)}` : '';
        return `May be listed by simulated players${simulated}${player}`;
    }
</script>

{#snippet conditionLines(lines: string[])}
    {#each lines as line (line)}
        <div class="text-zinc-500">{line}</div>
    {/each}
{/snippet}

{#snippet entranceButtons(entries: WorldZoneLine[])}
    {#each entries as entrance (entrance.stableKey)}
        <button
            type="button"
            class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-zinc-400 hover:bg-zinc-700/50 hover:text-white"
            onmouseenter={() => onHoverSpawn(entrance.stableKey)}
            onmouseleave={() => onHoverSpawn(null)}
            onclick={() => onFocusSpawn(entrance.stableKey)}
        >
            <span>{entrance.destinationContext ? entrance.destinationZoneName : `Enter from ${entrance.zoneName} through ${entrance.destinationZoneName}`}</span>
            <Crosshair class="h-3.5 w-3.5 shrink-0" />
        </button>
    {/each}
{/snippet}

<div class="space-y-4">
    <!-- Summary -->
    <div class="relative flex items-center justify-center">
        {#if result.iconHash}
            <img src={`/items/${result.iconHash}.w48.webp`} alt="" class="h-12 w-12" />
        {/if}
        <div class="absolute right-0">
            <WikiLink pageName={result.wikiPageName} />
        </div>
    </div>

    {#if allMarkers.length > 0}
        <!-- Focus all button -->
        <button
            type="button"
            onclick={() => onFocusAll()}
            onmouseenter={() => onHoverSpawn(markerKeys(allMarkers))}
            onmouseleave={() => onHoverSpawn(null)}
            class="flex w-full items-center justify-center gap-2 rounded-md
                   bg-zinc-700/50 px-3 py-2 text-xs text-zinc-300
                   hover:bg-zinc-700 hover:text-white transition-colors"
        >
            <Crosshair class="h-3.5 w-3.5" />
            <span>Show all {allMarkers.length} location{allMarkers.length !== 1 ? 's' : ''}</span>
        </button>
    {:else if !result.hasKnownSource}
        <p class="border-t border-zinc-700 pt-3 text-center text-xs text-zinc-400">
            The map has no data on how to obtain this item.
        </p>
    {/if}

    {#if vendorsByZone.length > 0}
        <!-- Sold by -->
        <div class="space-y-3 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500">Sold by</div>
            {#each vendorsByZone as group (group.zone)}
                <div>
                    <div class="flex items-center justify-between mb-1.5">
                        <div class="text-xs font-medium text-zinc-300">{group.zoneName}</div>
                        <div class="text-xs text-zinc-500">
                            {characterCount(group.rows)} vendor{characterCount(group.rows) !== 1 ? 's' : ''}
                        </div>
                    </div>
                    <div class="space-y-1">
                        {#each group.rows as vendor (`${group.zone}:${vendor.source.key}`)}
                            <button
                                type="button"
                                data-source-keys={sourceKeys(vendor.source.sourceKeys)}
                                class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                                       text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                                       transition-colors group"
                                onmouseenter={() => onHoverSpawn(markerKeys(vendor.spawns))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(vendor.spawns)}
                            >
                                <div class="min-w-0 flex-1">
                                    <div class="text-zinc-300">
                                        <span class="truncate">{vendor.row.npcName}</span>
                                    </div>
                                    <div class="flex flex-wrap items-center gap-x-1 text-zinc-500">
                                        <span>{formatPrice(vendor.row.price)} gold</span>
                                        <span>·</span>
                                        <span>
                                            {vendor.spawns.length} location{vendor.spawns.length !==
                                            1
                                                ? 's'
                                                : ''}
                                        </span>
                                    </div>
                                    <div class="text-zinc-500">{@render conditionLines(vendor.source.conditions)}</div>
                                </div>
                                <Crosshair
                                    class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                                />
                            </button>
                        {/each}
                    </div>
                </div>
            {/each}
        </div>
    {/if}

    {#if unlocatedVendors.length}
        <!-- Shown after the located sold by entries, under their heading when they exist. -->
        <div class="space-y-2 pt-2 text-xs" class:border-t={!vendorsByZone.length} class:border-zinc-700={!vendorsByZone.length}>
            {#if !vendorsByZone.length}<div class="uppercase tracking-wide text-zinc-500">Sold by</div>{/if}
            {#each unlocatedVendors as source (source.key)}
                <div data-source-keys={sourceKeys(source.sourceKeys)}>
                    <div class="flex items-center gap-1 text-zinc-300">
                        {source.row.npcName}<WikiLink pageName={source.row.npcWikiPageName} />
                    </div>
                    <div class="text-zinc-400">{formatPrice(source.row.price)} gold · Location unknown</div>
                    <div class="text-zinc-500">{@render conditionLines(source.conditions)}</div>
                </div>
            {/each}
        </div>
    {/if}

    {#if giversByZone.length || unlocatedGivers.length || uiGrants.length}
        <div class="space-y-3 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500">Given by</div>
            {#each giversByZone as group (group.zone)}
                <div class="space-y-1">
                    <div class="text-xs font-medium text-zinc-300">{group.zoneName}</div>
                    {#each group.rows as giver (`${group.zone}:${giver.source.key}`)}
                        <div class="rounded px-2 py-1.5 text-xs text-zinc-400" data-source-keys={sourceKeys(giver.source.sourceKeys)}>
                            <button
                                type="button"
                                class="flex w-full items-center justify-between text-left text-zinc-300 hover:text-white"
                                onmouseenter={() => onHoverSpawn(markerKeys(giver.spawns))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(giver.spawns)}
                            >
                                <span
                                    >{giver.row.npcName} · {giver.spawns.length} location{giver
                                        .spawns.length !== 1
                                        ? 's'
                                        : ''}</span
                                >
                                <Crosshair class="h-3.5 w-3.5 shrink-0" />
                            </button>
                            <div class="mt-1">{@render conditionLines(giver.source.conditions)}</div>
                        </div>
                    {/each}
                </div>
            {/each}
            {#each unlocatedGivers as source (source.key)}
                <div class="px-2 text-xs text-zinc-400" data-source-keys={sourceKeys(source.sourceKeys)}>
                    <div class="flex items-center gap-1 text-zinc-300">
                        {source.row.npcName}<WikiLink pageName={source.row.npcWikiPageName} />
                    </div>
                    <div>Location unknown</div>
                    {@render conditionLines(source.conditions)}
                </div>
            {/each}
            {#each uiGrants as source (source.key)}
                <div class="px-2 text-xs text-zinc-400" data-source-keys={sourceKeys(source.sourceKeys)}>
                    {#if source.markers.length}
                        <button
                            type="button"
                            class="flex w-full items-center justify-between text-left text-zinc-300 hover:text-white"
                            onmouseenter={() => onHoverSpawn(markerKeys(source.markers))}
                            onmouseleave={() => onHoverSpawn(null)}
                            onclick={() => focusMarkers(source.markers)}
                        >
                            <span>{source.row.name} · {source.markers[0].zoneName}</span>
                            <Crosshair class="h-3.5 w-3.5 shrink-0" />
                        </button>
                    {:else}
                        <div class="flex items-center gap-1 text-zinc-300">
                            {source.row.name}<WikiLink pageName={source.row.wikiPageName} />
                        </div>
                        <div>{source.row.zoneName ?? 'Location unknown'}</div>
                    {/if}
                    {@render entranceButtons(source.entries)}
                    {@render conditionLines(source.conditions)}
                </div>
            {/each}
        </div>
    {/if}

    {#if quests.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Reward from</div>
            {#each quests as quest (quest.row.questStableKey)}
                <div class="space-y-1" data-source-keys={sourceKeys(quest.sourceKeys)}>
                    <div class="flex items-center gap-1">
                        {quest.row.questName}<WikiLink pageName={quest.row.questWikiPageName} />
                    </div>
                    <div class="text-zinc-400">{@render conditionLines(quest.shared)}</div>
                    {#each quest.turnIns as turnIn (turnIn.key)}
                        {#each [...new Set(turnIn.markers.map((m) => m.zone))] as zone (zone)}
                            {@const markers = turnIn.markers.filter((m) => m.zone === zone)}
                            <button
                                type="button"
                                class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-zinc-400 hover:bg-zinc-700/50 hover:text-white"
                                onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(markers)}
                            >
                                <span>Turn in to {turnIn.row.turnInCharacterName} · {markers[0].zoneName}</span>
                                <Crosshair class="h-3.5 w-3.5 shrink-0" />
                            </button>
                        {:else}
                            <div class="px-2 text-zinc-400">Turn in to {turnIn.row.turnInCharacterName} · Location unknown</div>
                        {/each}
                        {@render entranceButtons(turnIn.entries)}
                        <div class="px-2 text-zinc-500">{@render conditionLines(turnIn.conditions)}</div>
                    {/each}
                </div>
            {/each}
        </div>
    {/if}

    {#if recipes.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Crafting recipe</div>
            {#each recipes as recipe (recipe.key)}
                <div data-source-keys={sourceKeys(recipe.sourceKeys)}>
                    <div class="flex items-center gap-1">
                        {recipe.row.recipeName}<WikiLink pageName={recipe.row.recipeWikiPageName} />
                    </div>
                    <div class="text-zinc-400">{@render conditionLines(recipe.conditions)}</div>
                </div>
            {/each}
            <p class="text-zinc-400">Crafted at a forge.</p>
        </div>
    {/if}

    {#if bagsByZone.length > 0}
        <!-- Item bags -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">Item bags</div>
            {#each bagsByZone as group (group.key)}
                {@const markers = [...group.markers.values()]}
                <button
                    type="button"
                    data-source-keys={sourceKeys(group.sourceKeys)}
                    class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                           text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                           transition-colors group"
                    onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                    onmouseleave={() => onHoverSpawn(null)}
                    onclick={() => focusMarkers(markers)}
                >
                    <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-x-1.5 text-zinc-300">
                            <span>{group.zoneName}</span>
                        </div>
                        <div class="text-zinc-500">
                            {markers.length} bag{markers.length !== 1 ? 's' : ''}
                        </div>
                        <div class="text-zinc-500">{@render conditionLines(group.conditions)}</div>
                    </div>
                    <Crosshair
                        class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                    />
                </button>
            {/each}
        </div>
    {/if}

    {#if starting.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Starting item of</div>
            {#if starting[0].row.allClasses}
                <div class="flex items-center gap-1" data-source-keys={sourceKeys(starting.flatMap((source) => source.sourceKeys))}>
                    All classes<WikiLink pageName="Classes" />
                </div>
            {:else}
                {#each starting as source (source.key)}
                    <div class="flex items-center gap-1" data-source-keys={sourceKeys(source.sourceKeys)}>
                        {source.row.classDisplayName}<WikiLink
                            pageName={source.row.classDisplayName}
                        />
                    </div>
                {/each}
            {/if}
        </div>
    {/if}

    {#if droppersByZone.length > 0}
        <!-- Dropped by -->
        <div class="space-y-3 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500">Dropped by</div>
            {#each droppersByZone as group (group.zone)}
                <div>
                    <div class="flex items-center justify-between mb-1.5">
                        <div class="text-xs font-medium text-zinc-300">{group.zoneName}</div>
                        <div class="text-xs text-zinc-500">
                            {characterCount(group.rows)} dropper{characterCount(group.rows) !== 1 ? 's' : ''}
                        </div>
                    </div>
                    <div class="space-y-1">
                        {#each group.rows as dropper (`${group.zone}:${dropper.source.key}`)}
                            <button
                                type="button"
                                data-source-keys={sourceKeys(dropper.source.sourceKeys)}
                                class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                                       text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                                       transition-colors group"
                                onmouseenter={() => onHoverSpawn(markerKeys(dropper.spawns))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(dropper.spawns)}
                            >
                                <div class="min-w-0 flex-1">
                                    <div
                                        class="flex flex-wrap items-center gap-x-1.5 text-zinc-300"
                                    >
                                        <span class="truncate">{dropper.row.npcName}</span>
                                        {#if dropper.row.encounterTier === 'boss'}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-amber-900/50 text-amber-300">Boss</span
                                            >
                                        {:else if dropper.row.encounterTier === 'elite'}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-indigo-900/50 text-indigo-300">Elite</span
                                            >
                                        {:else if dropper.row.encounterTier === 'chest'}
                                            <span
                                                class="rounded px-1 py-0.5 text-[10px]
                                                       bg-teal-900/50 text-teal-300">Chest</span
                                            >
                                        {/if}
                                    </div>
                                    <div class="flex flex-wrap items-center gap-x-1 text-zinc-500">
                                        <span>{dropText(dropper.row.dropProbability)}</span>
                                        <span>·</span>
                                        <span>
                                            {dropper.spawns.length} spawn{dropper.spawns.length !==
                                            1
                                                ? 's'
                                                : ''}
                                        </span>
                                    </div>
                                    <div class="text-zinc-500">{@render conditionLines(dropper.source.conditions)}</div>
                                </div>
                                <Crosshair
                                    class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                                />
                            </button>
                        {/each}
                    </div>
                </div>
            {/each}
        </div>
    {/if}

    {#if unlocatedDroppers.length}
        <!-- Shown after the located dropped by entries, under their heading when they exist. -->
        <div class="space-y-2 pt-2 text-xs" class:border-t={!droppersByZone.length} class:border-zinc-700={!droppersByZone.length}>
            {#if !droppersByZone.length}<div class="uppercase tracking-wide text-zinc-500">Dropped by</div>{/if}
            {#each unlocatedDroppers as source (source.key)}
                <div data-source-keys={sourceKeys(source.sourceKeys)}>
                    <div class="flex items-center gap-1 text-zinc-300">
                        {source.row.npcName}<WikiLink pageName={source.row.npcWikiPageName} />
                    </div>
                    <div class="text-zinc-400">{dropText(source.row.dropProbability)} · Location unknown</div>
                    <div class="text-zinc-500">{@render conditionLines(source.conditions)}</div>
                </div>
            {/each}
        </div>
    {/if}

    {#if treasureGroups.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs">
            <div class="uppercase tracking-wide text-zinc-500">Treasure hunting</div>
            <p class="text-zinc-400">Possible hunt locations, not chests present at every site.</p>
            {#each treasureGroups as group (group.key)}
                <div class="space-y-1" data-source-keys={sourceKeys(group.sourceKeys)}>
                    <div class="flex items-center gap-1 text-zinc-300">
                        {group.row.chestName}<WikiLink pageName={group.row.chestWikiPageName} />
                    </div>
                    <button
                        type="button"
                        class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-zinc-400 hover:bg-zinc-700/50 hover:text-white"
                        onmouseenter={() => onHoverSpawn(markerKeys(group.markers))}
                        onmouseleave={() => onHoverSpawn(null)}
                        onclick={() => focusMarkers(group.markers)}
                    >
                        <span>
                            {group.zoneName} · player levels {group.row.playerLevelMin}–{group.row.playerLevelMax}
                            <br />{group.markers.length} possible location{group.markers.length !== 1 ? 's' : ''}
                            · {dropText(group.row.dropProbability)}
                            {@render conditionLines(group.conditions)}
                        </span>
                        <Crosshair class="h-3.5 w-3.5 shrink-0" />
                    </button>
                </div>
            {/each}
        </div>
    {/if}

    {#if miningByZone.length > 0}
        <!-- Mining nodes -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">Mining nodes</div>
            {#each miningByZone as group (group.key)}
                {@const entries = [...group.entries.values()]}
                {@const markers = entries.map((entry) => entry.marker)}
                {@const chances = entries.flatMap((entry) => entry.chances)}
                <button
                    type="button"
                    data-source-keys={sourceKeys(group.sourceKeys)}
                    class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                           text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                           transition-colors group"
                    onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                    onmouseleave={() => onHoverSpawn(null)}
                    onclick={() => focusMarkers(markers)}
                >
                    <div class="min-w-0 flex-1">
                        <div class="text-zinc-300">{group.zoneName}</div>
                        <div class="text-zinc-500">
                            {entries.length} node{entries.length !== 1 ? 's' : ''} ·
                            {formatChanceRange(chances)} chance
                        </div>
                        <div class="text-zinc-500">{@render conditionLines(group.conditions)}</div>
                    </div>
                    <Crosshair
                        class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                    />
                </button>
            {/each}
        </div>
    {/if}

    {#if fishingByZone.length > 0 || anyWater.length > 0}
        <!-- Fishing spots -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">Fishing spots</div>
            {#each fishingByZone as group (group.key)}
                {@const entries = [...group.entries.values()]}
                {@const markers = entries.map((entry) => entry.marker)}
                {@const chances = entries.flatMap((entry) => entry.chances)}
                {@const periods = entries.flatMap((entry) => [...entry.periods])}
                <button
                    type="button"
                    data-source-keys={sourceKeys(group.sourceKeys)}
                    class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left
                           text-xs text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-200
                           transition-colors group"
                    onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                    onmouseleave={() => onHoverSpawn(null)}
                    onclick={() => focusMarkers(markers)}
                >
                    <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-x-1.5 text-zinc-300">
                            <span>{group.zoneName}</span>
                            {#if periods.every((period) => period === 'day')}
                                <span
                                    class="rounded px-1 py-0.5 text-[10px] bg-sky-900/50 text-sky-300"
                                >
                                    Day
                                </span>
                            {:else if periods.every((period) => period === 'night')}
                                <span
                                    class="rounded px-1 py-0.5 text-[10px]
                                           bg-indigo-900/50 text-indigo-300">Night</span
                                >
                            {/if}
                        </div>
                        <div class="text-zinc-500">
                            {entries.length} spot{entries.length !== 1 ? 's' : ''} ·
                            {formatChanceRange(chances)} chance
                        </div>
                        <div class="text-zinc-500">{@render conditionLines(group.conditions)}</div>
                    </div>
                    <Crosshair
                        class="h-3.5 w-3.5 shrink-0 text-zinc-600 group-hover:text-zinc-400"
                    />
                </button>
            {/each}
            {#each anyWater as source (source.key)}
                <!-- A catch from the global fishing roll, available at every water, so it has no location. -->
                <div class="px-2 py-1.5 text-xs" data-source-keys={sourceKeys(source.sourceKeys)}>
                    <div class="text-zinc-300">Any water</div>
                    <div class="text-zinc-500">
                        {formatChanceRange(source.row.dropChance === null ? [] : [source.row.dropChance])} chance
                    </div>
                    <div class="text-zinc-500">{@render conditionLines(source.conditions)}</div>
                </div>
            {/each}
        </div>
    {/if}

    {#if itemUses.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs text-zinc-300">
            <div class="uppercase tracking-wide text-zinc-500">Obtained by using</div>
            {#each itemUses as source (source.key)}
                <div data-source-keys={sourceKeys(source.sourceKeys)}>
                    <div class="flex items-center gap-1">
                        {source.row.sourceItemName}<WikiLink
                            pageName={source.row.sourceItemWikiPageName}
                        />
                    </div>
                    {#if source.row.dropProbability !== null}<div class="text-zinc-400">
                            {formatWorldDropChance(source.row.dropProbability)}
                        </div>{/if}
                    {#if source.row.zoneName}<div class="text-zinc-400">
                            in {source.row.zoneName}
                        </div>{/if}
                    <div class="text-zinc-400">{@render conditionLines(source.conditions)}</div>
                </div>
            {/each}
        </div>
    {/if}

    {#if commonWorldDrops.length > 0}
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">World drop</div>
            {#each commonWorldDrops as source (source.key)}
                <div class="px-2 text-xs text-zinc-300" data-source-keys={sourceKeys(source.sourceKeys)}>
                    {commonWorldSourceLabel(source.row.dropProbability ?? 0, source.row.dropProbabilityMax ?? source.row.dropProbability ?? 0)}
                    <div class="text-zinc-500">{@render conditionLines(source.conditions)}</div>
                </div>
            {/each}
        </div>
    {/if}

    {#if worldDrops.length > 0}
        <!-- Special world drops -->
        <div class="space-y-1 border-t border-zinc-700 pt-2">
            <div class="text-xs uppercase tracking-wide text-zinc-500 mb-2">World drop</div>
            {#each worldDrops as drop (drop.key)}
                <div class="px-2 text-xs" data-source-keys={sourceKeys(drop.sourceKeys)}>
                    <div class="flex justify-between gap-2">
                        <span class="text-zinc-300">
                            {drop.row.minLevelExclusive > 0
                                ? `Any enemy above level ${drop.row.minLevelExclusive}`
                                : 'Any enemy'}
                        </span>
                        {#if drop.row.dropProbability !== null}
                            <span class="shrink-0 text-zinc-500"
                                >{formatWorldDropChance(drop.row.dropProbability)} per kill</span
                            >
                        {/if}
                    </div>
                    <div class="text-zinc-500">{@render conditionLines(drop.conditions)}</div>
                </div>
            {/each}
            <div class="px-2 text-xs text-zinc-500">At the default loot rate.</div>
        </div>
    {/if}
    {#if auctionHouses.length}
        <div class="space-y-2 border-t border-zinc-700 pt-2 text-xs">
            <div class="flex items-center gap-1 text-zinc-300">
                Auction House<WikiLink pageName="Auction House" />
            </div>
            {#each auctionHouses as source (source.key)}
                <div class="text-zinc-400" data-source-keys={sourceKeys(source.sourceKeys)}>
                    <p>{auctionAvailability(source.row)}</p>
                    {@render conditionLines(source.conditions)}
                </div>
            {/each}
            <p class="text-zinc-500">Stock is random.</p>
            {#each auctionHouses as source (source.key)}
                {#each source.brokers as broker (broker.row.characterStableKey)}
                    <div class="space-y-1">
                        <div class="flex items-center gap-1 text-zinc-300">
                            {broker.row.npcName}<WikiLink pageName={broker.row.npcWikiPageName} />
                        </div>
                        {#each [...new Set(broker.markers.map((marker) => marker.zone))] as zone (zone)}
                            {@const markers = broker.markers.filter((marker) => marker.zone === zone)}
                            <button
                                type="button"
                                class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-zinc-400 hover:bg-zinc-700/50 hover:text-white"
                                onmouseenter={() => onHoverSpawn(markerKeys(markers))}
                                onmouseleave={() => onHoverSpawn(null)}
                                onclick={() => focusMarkers(markers)}
                            >
                                <span>{markers[0].zoneName} · {markers.length} location{markers.length !== 1 ? 's' : ''}</span>
                                <Crosshair class="h-3.5 w-3.5 shrink-0" />
                            </button>
                        {:else}
                            <div class="text-zinc-400">Location unknown</div>
                        {/each}
                    </div>
                {/each}
            {/each}
        </div>
    {/if}

</div>

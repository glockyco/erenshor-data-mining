/**
 * Arranges one item's public sources in the item panel's established rows: a vendor or
 * dropper with its price or chance, each treasure tier, node, water and bag.
 *
 * Locations that need different conditions form separate rows, so a row's counts and
 * conditions hold for every location it lists. Reliquary rooms differ only in the
 * furnishing they need, so copies that differ only there share one row and one condition.
 */
import { conditionPhrases, playerLevelPhrase, type ProvenanceCondition, type ProvenanceLocation } from '$lib/item-provenance';
import type { EncounterTier } from '$lib/map-markers';
import type { WorldItemBag, WorldMiningNode, WorldTreasureLoc, WorldWater, WorldZoneLine } from '$lib/types/world-map';
import type { AnySourceMarker, AnySpawnMarker, ItemSearchProvider, ResolvedItemSource } from './item-source-provider';

export interface PresentedCharacter {
    characterStableKey: string;
    npcName: string;
    npcWikiPageName: string | null;
}

interface Shown {
    /** Unique among one item's presented sources. */
    key: string;
    sourceKeys: string[];
    conditions: string[];
}

export type PresentedItemSource = Shown & (
    | { kind: 'drop'; row: PresentedCharacter & { encounterTier: EncounterTier | null; dropProbability: number | null }; markers: AnySpawnMarker[] }
    | { kind: 'vendor'; row: PresentedCharacter & { price: number }; markers: AnySpawnMarker[] }
    | { kind: 'dialog'; row: PresentedCharacter; markers: AnySpawnMarker[] }
    | { kind: 'ui_grant'; row: { name: string; wikiPageName: string | null; zoneName: string | null }; markers: AnySpawnMarker[]; entries: WorldZoneLine[] }
    | {
        kind: 'quest';
        row: { questStableKey: string; questName: string; questWikiPageName: string | null; turnInCharacterStableKey: string; turnInCharacterName: string };
        markers: AnySpawnMarker[];
        entries: WorldZoneLine[];
    }
    | {
        kind: 'auction_house';
        /** Level windows of the routes that list the item, merged where they overlap. */
        row: { simulatedPlayerLevels: string[]; playerLevels: string[] };
        markers: AnySpawnMarker[];
        brokers: { row: PresentedCharacter; markers: AnySpawnMarker[] }[];
    }
    | {
        kind: 'treasure';
        row: { characterStableKey: string; chestName: string; chestWikiPageName: string | null; playerLevelMin: number | null; playerLevelMax: number | null; dropProbability: number | null };
        markers: WorldTreasureLoc[];
    }
    | { kind: 'mining'; row: { dropChance: number | null }; marker: WorldMiningNode }
    | { kind: 'fishing'; row: { period: 'day' | 'night' | null; dropChance: number | null }; marker: WorldWater }
    | { kind: 'any_water'; row: { dropChance: number | null } }
    | { kind: 'bag'; marker: WorldItemBag }
    | { kind: 'world'; row: { dropProbability: number | null; minLevelExclusive: number } }
    | { kind: 'common_world_item'; row: { dropProbability: number | null; dropProbabilityMax: number | null } }
    | { kind: 'craft'; row: { recipeStableKey: string; recipeName: string; recipeWikiPageName: string | null } }
    | { kind: 'item_use'; row: { sourceItemStableKey: string; sourceItemName: string; sourceItemWikiPageName: string | null; dropProbability: number | null; zoneName: string | null } }
    | { kind: 'starting'; row: { className: string; classDisplayName: string; allClasses: boolean } }
);
type Grouped = Extract<PresentedItemSource, { markers: AnySpawnMarker[] }>;

interface PlaceGroup {
    places: ProvenanceLocation[];
    markers: AnySourceMarker[];
    conditions: string[];
    /** Room furnishing atoms, worded once for every copy that shares the row. */
    furnishings: ProvenanceCondition[];
}

/**
 * Splits a source's places by the conditions they need and by whether the map places them.
 * `omit` drops source conditions that the row already shows in its established form.
 */
function placeGroups(source: ResolvedItemSource, omit: (atom: ProvenanceCondition) => boolean = () => false): PlaceGroup[] {
    const fact = source.row.provenance;
    const context = { itemStableKey: fact.item_stable_key, rewardQuestStableKey: fact.kind === 'quest_reward' ? fact.source_stable_key : null };
    const markers = new Map(source.markers.map((marker) => [marker.stableKey, marker]));
    const groups = new Map<string, PlaceGroup>();
    for (const place of fact.locations.length ? fact.locations : [null]) {
        const atoms = place?.conditions ?? [];
        // A furnishing atom in a gate without alternatives is a plain requirement of its room.
        const branched = new Set(atoms.filter((atom) => atom.alternative_index > 0).map((atom) => atom.gate_index));
        const furnishings = atoms.filter((atom) => atom.predicate === 'room_furnished' && !branched.has(atom.gate_index));
        const conditions = conditionPhrases([fact.conditions.filter((atom) => !omit(atom)), atoms.filter((atom) => !furnishings.includes(atom))],
            source.row.referenceNames, context);
        // Treasure rows show their eligible levels in their established form.
        if (place && place.relation !== 'possible_treasure' && (place.player_level_min !== null || place.player_level_max !== null)) {
            conditions.push(playerLevelPhrase(place.player_level_min, place.player_level_max));
        }
        const marker = place?.marker_stable_key && place.relation !== 'unlocated' ? markers.get(place.marker_stable_key) : undefined;
        const key = JSON.stringify([conditions, furnishings.length > 0, marker !== undefined]);
        const group = groups.get(key) ?? { places: [], markers: [], conditions, furnishings: [] };
        if (place) group.places.push(place);
        if (marker && !group.markers.includes(marker)) group.markers.push(marker);
        group.furnishings.push(...furnishings);
        groups.set(key, group);
    }
    return [...groups.values()];
}

function spawnMarkers(markers: AnySourceMarker[]): AnySpawnMarker[] {
    return markers.filter((marker): marker is AnySpawnMarker => 'characters' in marker);
}

function chance(source: ResolvedItemSource): number | null {
    return source.row.provenance.probability_max ?? source.row.provenance.probability_min;
}

/** Zone lines that lead to places the map cannot show, such as instanced rooms. */
function entrances(source: ResolvedItemSource, group: PlaceGroup): WorldZoneLine[] {
    return [...new Set(group.places.flatMap((place) => place.entry_zone_line_keys))]
        .flatMap((entry) => source.entries.filter((candidate) => candidate.stableKey === entry));
}

function character(source: ResolvedItemSource): PresentedCharacter {
    const fact = source.row.provenance;
    return {
        characterStableKey: source.row.characterStableKey ?? fact.source_group_key ?? fact.source_stable_key ?? fact.source_key,
        npcName: source.row.sourceName,
        npcWikiPageName: source.row.sourceWikiPageName
    };
}

/**
 * Presents an item's resolved public sources. `startingClassCount` is the number of
 * classes with starting items, so an item that every class starts with reads "All classes".
 */
export function presentItemSources(sources: ResolvedItemSource[], startingClassCount: number): PresentedItemSource[] {
    const presented: PresentedItemSource[] = [];
    // Copies of one character with equal terms share a row, as one character always has.
    const grouped = new Map<string, { row: Grouped; furnishings: ProvenanceCondition[]; names: Record<string, string> }>();
    function merge(identity: unknown[], source: ResolvedItemSource, group: PlaceGroup, create: (key: string) => Grouped): void {
        const key = JSON.stringify([...identity, group.conditions, group.furnishings.length > 0, group.markers.length > 0]);
        const entry = grouped.get(key) ?? { row: create(key), furnishings: [], names: source.row.referenceNames };
        grouped.set(key, entry);
        if (!entry.row.sourceKeys.includes(source.row.provenance.source_key)) entry.row.sourceKeys.push(source.row.provenance.source_key);
        for (const marker of spawnMarkers(group.markers)) if (!entry.row.markers.includes(marker)) entry.row.markers.push(marker);
        entry.furnishings.push(...group.furnishings);
    }
    const startingClasses = new Set(sources.filter((source) => source.row.provenance.kind === 'starting_class')
        .map((source) => source.row.provenance.source_stable_key));
    const auctionLevels = { sim: [] as [number, number][], player: [] as [number, number][] };
    for (const source of sources) {
        const fact = source.row.provenance;
        const names = source.row.referenceNames;
        const sourceKeys = [fact.source_key];
        const base = (key: string) => ({ key, sourceKeys: [] as string[], markers: [] as AnySpawnMarker[] });
        if (source.presentation === 'any_water') {
            presented.push({ kind: 'any_water', key: fact.source_key, sourceKeys, row: { dropChance: chance(source) },
                conditions: conditionPhrases([fact.conditions], names, { itemStableKey: fact.item_stable_key }) });
            continue;
        }
        switch (fact.kind) {
            case 'character_drop': {
                const who = character(source);
                for (const group of placeGroups(source)) {
                    const sites = group.places.filter((place) => place.relation === 'possible_treasure');
                    for (const place of sites) {
                        const marker = group.markers.find((candidate) => candidate.stableKey === place.marker_stable_key) as WorldTreasureLoc | undefined;
                        presented.push({ kind: 'treasure', key: `${fact.source_key}:${place.marker_stable_key ?? place.place_key}`, sourceKeys, conditions: group.conditions,
                            markers: marker ? [marker] : [], row: { characterStableKey: who.characterStableKey, chestName: who.npcName,
                                chestWikiPageName: who.npcWikiPageName, playerLevelMin: place.player_level_min, playerLevelMax: place.player_level_max,
                                dropProbability: chance(source) } });
                    }
                    if (sites.length === group.places.length && sites.length > 0) continue;
                    const markers = spawnMarkers(group.markers.filter((marker) => !sites.some((place) => place.marker_stable_key === marker.stableKey)));
                    const tier = markers.flatMap((marker) => marker.characters).find((entry) => entry.stableKey === who.characterStableKey)?.encounterTier ?? null;
                    merge(['drop', who.characterStableKey, chance(source)], source, { ...group, markers }, (key) => ({ ...base(key), kind: 'drop',
                        conditions: group.conditions, row: { ...who, encounterTier: tier, dropProbability: chance(source) } }));
                }
                break;
            }
            case 'vendor': {
                const who = character(source);
                for (const group of placeGroups(source)) {
                    merge(['vendor', who.characterStableKey, source.row.price], source, group, (key) => ({ ...base(key), kind: 'vendor',
                        conditions: group.conditions, row: { ...who, price: source.row.price ?? 0 } }));
                }
                break;
            }
            case 'dialog': {
                const who = character(source);
                for (const group of placeGroups(source)) {
                    merge(['dialog', who.characterStableKey], source, group, (key) => ({ ...base(key), kind: 'dialog', conditions: group.conditions, row: who }));
                }
                break;
            }
            case 'ui_grant': {
                for (const group of placeGroups(source)) {
                    const zone = group.places.find((place) => place.zone_stable_key || place.scene);
                    merge(['ui_grant', fact.source_key], source, group, (key) => ({ ...base(key), kind: 'ui_grant', conditions: group.conditions,
                        entries: entrances(source, group),
                        row: { name: source.row.sourceName, wikiPageName: source.row.sourceWikiPageName,
                            zoneName: zone ? names[zone.zone_stable_key ?? ''] ?? zone.scene : null } }));
                }
                break;
            }
            case 'quest_reward': {
                for (const group of placeGroups(source)) {
                    const copy = group.places.find((place) => place.source_copy_stable_key)?.source_copy_stable_key ?? source.row.characterStableKey ?? fact.source_key;
                    const turnIn = source.row.locationSources[copy]?.name ?? names[copy] ?? '';
                    merge(['quest', fact.source_stable_key, turnIn], source, group, (key) => ({ ...base(key), kind: 'quest', conditions: group.conditions,
                        entries: entrances(source, group),
                        row: { questStableKey: fact.source_stable_key ?? fact.source_key, questName: source.row.sourceName,
                            questWikiPageName: source.row.sourceWikiPageName, turnInCharacterStableKey: copy, turnInCharacterName: turnIn } }));
                }
                break;
            }
            case 'auction_house': {
                let row = presented.find((candidate) => candidate.kind === 'auction_house');
                if (!row) {
                    row = { kind: 'auction_house', key: 'auction_house', sourceKeys: [], conditions: [], markers: [], brokers: [],
                        row: { simulatedPlayerLevels: [], playerLevels: [] } };
                    presented.push(row);
                }
                if (row.kind !== 'auction_house') break;
                row.sourceKeys.push(fact.source_key);
                // The established sentence about simulated players carries each route's level window.
                const levels = fact.conditions.filter((atom) => atom.predicate === 'actor_level' && atom.minimum !== null && atom.maximum !== null &&
                    atom.minimum_inclusive && atom.maximum_inclusive && (atom.actor === 'sim' || atom.actor === 'sim_player' || atom.actor === 'player'));
                for (const atom of levels) (atom.actor === 'player' ? auctionLevels.player : auctionLevels.sim).push([atom.minimum!, atom.maximum!]);
                for (const group of placeGroups(source, (atom) => levels.includes(atom))) {
                    for (const condition of group.conditions) if (!row.conditions.includes(condition)) row.conditions.push(condition);
                    for (const place of group.places) {
                        const copy = place.source_copy_stable_key ?? place.marker_stable_key ?? place.place_key;
                        const label = source.row.locationSources[copy];
                        let broker = row.brokers.find((candidate) => candidate.row.characterStableKey === copy);
                        if (!broker) {
                            broker = { row: { characterStableKey: copy, npcName: label?.name ?? copy, npcWikiPageName: label?.wikiPageName ?? null }, markers: [] };
                            row.brokers.push(broker);
                        }
                        const marker = spawnMarkers(group.markers).find((candidate) => candidate.stableKey === place.marker_stable_key);
                        if (marker && !broker.markers.includes(marker)) broker.markers.push(marker);
                        if (marker && !row.markers.includes(marker)) row.markers.push(marker);
                    }
                }
                break;
            }
            case 'mining':
            case 'fishing':
            case 'item_bag': {
                // The established fishing rows show the period as a Day or Night tag.
                const period = fact.conditions.find((atom) => atom.predicate === 'time_of_day')?.value;
                for (const group of placeGroups(source, (atom) => fact.kind === 'fishing' && atom.predicate === 'time_of_day')) {
                    for (const marker of group.markers) {
                        const key = `${fact.source_key}:${marker.stableKey}`;
                        if (fact.kind === 'mining') presented.push({ kind: 'mining', key, sourceKeys, conditions: group.conditions,
                            marker: marker as WorldMiningNode, row: { dropChance: chance(source) } });
                        else if (fact.kind === 'fishing') presented.push({ kind: 'fishing', key, sourceKeys, conditions: group.conditions,
                            marker: marker as WorldWater, row: { period: period === 'day' || period === 'night' ? period : null, dropChance: chance(source) } });
                        else presented.push({ kind: 'bag', key, sourceKeys, conditions: group.conditions, marker: marker as WorldItemBag });
                    }
                }
                break;
            }
            case 'special_world_drop': {
                // The established row names the lowest enemy level, so that condition is not repeated below it.
                const level = fact.conditions.find((atom) => atom.predicate === 'actor_level' && atom.actor === 'enemy' && atom.maximum === null && atom.minimum !== null);
                presented.push({ kind: 'world', key: fact.source_key, sourceKeys, row: { dropProbability: chance(source),
                    minLevelExclusive: level ? level.minimum! - (level.minimum_inclusive ? 1 : 0) : 0 },
                conditions: conditionPhrases([fact.conditions.filter((atom) => atom !== level)], names) });
                break;
            }
            case 'common_world_item':
                presented.push({ kind: 'common_world_item', key: fact.source_key, sourceKeys,
                    row: { dropProbability: fact.probability_min, dropProbabilityMax: fact.probability_max },
                    conditions: conditionPhrases([fact.conditions], names) });
                break;
            case 'crafting':
                presented.push({ kind: 'craft', key: fact.source_key, sourceKeys, row: { recipeStableKey: fact.source_stable_key ?? fact.source_key,
                    recipeName: source.row.sourceName, recipeWikiPageName: source.row.sourceWikiPageName },
                conditions: conditionPhrases([fact.conditions], names) });
                break;
            case 'item_drop':
            case 'spell_created':
            case 'item_conversion': {
                // The established row names the zone where the item must be used.
                const zone = fact.conditions.find((atom) => atom.predicate === 'zone_use' && atom.reference_stable_key);
                presented.push({ kind: 'item_use', key: fact.source_key, sourceKeys, row: { sourceItemStableKey: fact.source_stable_key ?? fact.source_key,
                    sourceItemName: source.row.sourceName, sourceItemWikiPageName: source.row.sourceWikiPageName,
                    dropProbability: fact.probability_kind === 'exact' || fact.probability_kind === 'bounded' ? chance(source) : null,
                    zoneName: zone ? names[zone.reference_stable_key!] ?? zone.reference_stable_key! : null },
                conditions: conditionPhrases([fact.conditions.filter((atom) => atom !== zone)], names) });
                break;
            }
            case 'starting_class':
                presented.push({ kind: 'starting', key: fact.source_key, sourceKeys, row: { className: fact.source_stable_key ?? fact.source_key,
                    classDisplayName: source.row.sourceName, allClasses: startingClasses.size === startingClassCount },
                conditions: conditionPhrases([fact.conditions], names) });
                break;
            default:
                throw new Error(`Unpresented public source kind: ${fact.kind}`);
        }
    }
    const auction = presented.find((row) => row.kind === 'auction_house');
    if (auction?.kind === 'auction_house') auction.row = { simulatedPlayerLevels: windows(auctionLevels.sim), playerLevels: windows(auctionLevels.player) };
    const drops: PresentedItemSource[] = [];
    for (const { row, furnishings, names } of grouped.values()) {
        // Every atom names a set that turns the copy on in its own room, so the row lists the sets as alternatives.
        if (furnishings.length) row.conditions = [...row.conditions, ...conditionPhrases([furnishings.map((atom) => ({ ...atom, gate_index: 0, alternative_index: 0 }))], names)];
        (row.kind === 'drop' ? drops : presented).push(row);
    }
    // The panel has always listed a dropper with a higher chance first among equals.
    return [...presented, ...drops.sort((a, b) => dropChance(b) - dropChance(a))];
}

function dropChance(row: PresentedItemSource): number {
    return row.kind === 'drop' ? row.row.dropProbability ?? -1 : -1;
}

/** Merges overlapping or adjacent level windows and words each as a range joined by an en dash. */
function windows(ranges: [number, number][]): string[] {
    const merged: [number, number][] = [];
    for (const [min, max] of [...ranges].sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
        const last = merged[merged.length - 1];
        if (last && min <= last[1] + 1) last[1] = Math.max(last[1], max);
        else merged.push([min, max]);
    }
    return merged.map(([min, max]) => min === max ? `${min}` : `${min}–${max}`);
}

/**
 * Public source keys that an item panel would not show, such as a gathering source whose
 * marker the page lacks or a source kind without a row. The page build fails on any.
 */
export function unpresentedSourceKeys(provider: ItemSearchProvider): string[] {
    return provider.buildIndex().flatMap(({ result }) => {
        if (result.type !== 'item') return [];
        const sources = provider.getSourcesForItem(result.itemStableKey);
        const shown = new Set(presentItemSources(sources, provider.startingClassCount).flatMap((row) => row.sourceKeys));
        return sources.map((source) => source.row.provenance.source_key).filter((key) => !shown.has(key));
    });
}

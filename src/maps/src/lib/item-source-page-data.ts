import type { ItemAcquisition, ProvenanceCondition, ProvenanceLocation } from './item-provenance';
import type { ItemSourceItemMeta, ItemSourceRow, MiningNodeItem } from './map-markers';
import type { MapMarkerData } from './types/world-map';

type Markers = Omit<MapMarkerData, 'zones' | 'itemSources'>;
type Label = { name: string; wikiPageName: string | null };
type Packed = [mask: number, ...values: unknown[]];
const SOURCE_DEFAULTS: Omit<ItemAcquisition, 'source_key' | 'source_copy_stable_key' | 'place_set_key' | 'conditions' | 'locations' | 'source_group_key' | 'probability_max'> & {
    source_group_key: string | null | undefined; probability_max: number | null | undefined
} = {
    item_stable_key: '', kind: '', source_stable_key: null, source_group_key: undefined,
    mechanic: null, probability_kind: 'exact', probability_min: null, probability_max: undefined,
    probability_basis: null, quantity_kind: 'exact', quantity_min: 1, quantity_max: 1,
    expected_quantity: null, guaranteed: false
};
const CONDITION_DEFAULTS: Omit<ProvenanceCondition, 'gate_key' | 'phase'> = {
    gate_index: 0, alternative_index: 0, atom_index: 0, predicate: '', reference_stable_key: null,
    reference_slot: null, actor: null, value: null, minimum: null, maximum: null,
    minimum_inclusive: true, maximum_inclusive: true
};
const PLACE_DEFAULTS: Omit<ProvenanceLocation, 'place_key' | 'entry_zone_line_keys' | 'conditions'> & {
    conditions: Packed[] | null; entry_zone_line_keys: string[] | null
} = {
    marker_stable_key: null, relation: 'source', scene: null, zone_stable_key: null, x: null, z: null,
    player_level_min: null, player_level_max: null, source_copy_stable_key: null,
    conditions: null, entry_zone_line_keys: null
};
const ROW_DEFAULTS = {
    itemStableKey: null as string | null, sourceName: null as string | null,
    sourceWikiPageName: null as string | null, characterStableKey: undefined as string | null | undefined,
    price: null as number | null
};

function placeDefaults(marker?: { zone: string; position: { x: number; y: number }; characters?: { stableKey: string }[] }) {
    if (!marker) return PLACE_DEFAULTS;
    return { ...PLACE_DEFAULTS, scene: marker.zone, x: marker.position.x, z: marker.position.y,
        source_copy_stable_key: marker.characters?.length === 1 ? marker.characters[0].stableKey : null };
}

function unpack<T extends object>(packed: Packed, defaults: T): T {
    const value = { ...defaults };
    let offset = 1;
    Object.keys(defaults).forEach((key, index) => {
        if (packed[0] & (1 << index)) value[key as keyof T] = packed[offset++] as T[keyof T];
    });
    return value;
}
type EncodedSource = [fact: Packed, places: number, row: Packed | null, conditions?: Packed[]];
type ReferencedItem = Omit<MiningNodeItem, 'provenance'> & { provenance: number };
export interface SerializedItemSourcePageData {
    itemSources: Record<string, EncodedSource>;
    itemPlaces: Packed[][];
    itemLabels: Record<string, Label>;
    markers: Omit<Markers, 'itemBags' | 'miningNodes' | 'water'> & {
        itemBags: (Omit<Markers['itemBags'][number], 'provenance'> & { provenance: number })[];
        miningNodes: (Omit<Markers['miningNodes'][number], 'items'> & { items: ReferencedItem[] })[];
        water: (Omit<Markers['water'][number], 'daytimeItems' | 'nighttimeItems'> & {
            daytimeItems: ReferencedItem[]; nighttimeItems: ReferencedItem[];
        })[];
    };
}
function labelsFromPage(markers: Markers | SerializedItemSourcePageData['markers'], items: ItemSourceItemMeta[]): Record<string, Label> {
    const labels: Record<string, Label> = {};
    for (const item of items) labels[item.itemStableKey] = { name: item.displayName, wikiPageName: item.wikiPageName };
    for (const marker of [...markers.npcs, ...markers.enemiesEnemy, ...markers.enemiesElite, ...markers.enemiesBoss, ...markers.enemiesChest]) {
        for (const character of marker.characters) labels[character.stableKey] = { name: character.name, wikiPageName: character.wikiPageName };
    }
    return labels;
}
/** Keep source identities once. All other joins use page-local references. */
export function serializeItemSourcePageData(rows: ItemSourceRow[], markers: Markers, allItems: ItemSourceItemMeta[]): SerializedItemSourcePageData {
    const shared = new Map<string, unknown[]>();
    // Devalue shares object identities, so equal tuples must share an object before serialization.
    function intern<T extends unknown[]>(values: T): T {
        const key = JSON.stringify(values);
        const existing = shared.get(key);
        if (existing) return existing as T;
        shared.set(key, values);
        return values;
    }
    /** A bit marks each non-default field, followed by its value in declaration order. */
    function pack<T extends object>(value: T, defaults: Partial<T>): Packed {
        let mask = 0;
        const values: unknown[] = [];
        Object.keys(defaults).forEach((key, index) => {
            if (value[key as keyof T] !== defaults[key as keyof T]) {
                mask |= 1 << index;
                values.push(value[key as keyof T]);
            }
        });
        return intern([mask, ...values]);
    }
    const itemSources: Record<string, EncodedSource> = {};
    const itemPlaces: Packed[][] = [];
    const itemLabels: Record<string, Label> = {};
    const labels = labelsFromPage(markers, allItems);
    const bySource = new Map<string, number>();
    const byPlaceSet = new Map<string, number>();
    const byMarker = new Map(Object.values(markers).flat().map((marker) => [marker.stableKey, marker]));
    const remember = (key: string, label: Label) => {
        if (labels[key]?.name !== label.name || labels[key]?.wikiPageName !== label.wikiPageName) itemLabels[key] = label;
    };
    for (const row of rows) {
        for (const [key, name] of Object.entries(row.referenceNames)) {
            remember(key, { name, wikiPageName: labels[key]?.wikiPageName ?? itemLabels[key]?.wikiPageName ?? null });
        }
        for (const [key, label] of Object.entries(row.locationSources)) remember(key, label);
    }
    Object.assign(labels, itemLabels);
    const conditions = (atoms: ProvenanceCondition[]) => intern(atoms.map((atom) => pack(atom, CONDITION_DEFAULTS)));
    function sourceReference(fact: ItemAcquisition, row: ItemSourceRow | null = null): number {
        const found = bySource.get(fact.source_key);
        if (found !== undefined) return found;
        let placeIndex = -1;
        if (fact.place_set_key) {
            const foundSet = byPlaceSet.get(fact.place_set_key);
            placeIndex = foundSet ?? itemPlaces.length;
            if (foundSet === undefined) {
                byPlaceSet.set(fact.place_set_key, placeIndex);
                itemPlaces.push(fact.locations.map((location) => {
                    const marker = location.marker_stable_key ? byMarker.get(location.marker_stable_key) : undefined;
                    return pack({
                        ...location, zone_stable_key: marker && location.relation !== 'unlocated' ? null : location.zone_stable_key,
                        conditions: location.conditions.length ? conditions(location.conditions) : null,
                        entry_zone_line_keys: location.entry_zone_line_keys.length ? location.entry_zone_line_keys : null
                    }, placeDefaults(marker));
                }));
            }
        }
        const label = labels[fact.source_stable_key ?? ''] ?? labels[row?.characterStableKey ?? ''];
        const presentation = row ? pack({
            itemStableKey: row.itemStableKey === fact.item_stable_key ? null : row.itemStableKey,
            sourceName: row.sourceName === label?.name ? null : row.sourceName,
            sourceWikiPageName: row.sourceWikiPageName === label?.wikiPageName ? null : row.sourceWikiPageName ?? '',
            characterStableKey: row.characterStableKey === fact.source_stable_key ? undefined : row.characterStableKey, price: row.price
        }, ROW_DEFAULTS) : null;
        const entry: EncodedSource = [pack({
            ...fact,
            // Only the global catch mechanic changes map presentation.
            mechanic: fact.mechanic === 'fishing_global_replacement' ? fact.mechanic : null,
            source_group_key: fact.source_group_key === fact.source_stable_key ? undefined : fact.source_group_key,
            probability_max: fact.probability_max === fact.probability_min ? undefined : fact.probability_max
        }, SOURCE_DEFAULTS), placeIndex, presentation];
        if (fact.conditions.length) entry.push(conditions(fact.conditions));
        const index = bySource.size;
        bySource.set(fact.source_key, index);
        itemSources[fact.source_key] = entry;
        return index;
    }
    for (const row of rows) sourceReference(row.provenance, row);
    const itemReference = (item: MiningNodeItem) => ({ ...item, provenance: sourceReference(item.provenance) });
    // Typed world-map popups do not read the HTML used by zone pages.
    const presentationMarkers = Object.fromEntries(Object.entries(markers).map(([kind, entries]) => [
        kind, entries.map((marker) => {
            const presentation = { ...marker };
            if ('popup' in presentation) delete presentation.popup;
            return presentation;
        })
    ])) as Markers;
    return { itemSources, itemPlaces, itemLabels, markers: { ...presentationMarkers,
        itemBags: presentationMarkers.itemBags.map((marker) => ({ ...marker, provenance: sourceReference(marker.provenance) })),
        miningNodes: presentationMarkers.miningNodes.map((marker) => ({ ...marker, items: marker.items.map(itemReference) })),
        water: presentationMarkers.water.map((marker) => ({ ...marker, daytimeItems: marker.daytimeItems.map(itemReference),
            nighttimeItems: marker.nighttimeItems.map(itemReference) }))
    } };
}

/** Resolve shared facts and display metadata once for search and typed popups. */
export function hydrateItemSourcePageData<T extends SerializedItemSourcePageData & { allItems: ItemSourceItemMeta[] }>(data: T): Omit<T, 'itemSources' | 'markers'> & {
    itemSources: ItemSourceRow[]; markers: Markers;
} {
    const labels = { ...labelsFromPage(data.markers, data.allItems), ...data.itemLabels };
    const referenceNames = Object.fromEntries(Object.entries(labels).map(([key, label]) => [key, label.name]));
    const items = new Map(data.allItems.map((item) => [item.itemStableKey, item]));
    const byMarker = new Map(Object.values(data.markers).flat().map((marker) => [marker.stableKey, marker]));
    const conditions = (atoms: Packed[] = []): ProvenanceCondition[] => atoms.map((atom) => ({
        ...unpack(atom, CONDITION_DEFAULTS), gate_key: '', phase: 'availability'
    } as ProvenanceCondition));
    const places: ProvenanceLocation[][] = data.itemPlaces.map((entries) => entries.map((packed, index) => {
        const markerKey = unpack(packed, PLACE_DEFAULTS).marker_stable_key;
        const marker = markerKey ? byMarker.get(markerKey) : undefined;
        const { conditions: atoms, entry_zone_line_keys: entrances, ...place } = unpack(packed, placeDefaults(marker));
        return { ...place,
            place_key: String(index), entry_zone_line_keys: entrances ?? [], conditions: conditions(atoms ?? []) };
    }));
    const entries = Object.entries(data.itemSources);
    const facts: ItemAcquisition[] = entries.map(([key, [packed, placeIndex, , atoms]]) => {
        const fact = unpack(packed, SOURCE_DEFAULTS);
        return { ...fact, source_key: key, source_copy_stable_key: null,
            source_group_key: fact.source_group_key === undefined ? fact.source_stable_key : fact.source_group_key,
            probability_max: fact.probability_max === undefined ? fact.probability_min : fact.probability_max,
            place_set_key: placeIndex < 0 ? null : String(placeIndex), locations: places[placeIndex] ?? [], conditions: conditions(atoms) };
    });
    const itemSources: ItemSourceRow[] = entries.flatMap(([, [, , packed]], index) => {
        if (!packed) return [];
        const row = unpack(packed, ROW_DEFAULTS);
        const provenance = facts[index];
        const item = items.get(row.itemStableKey ?? provenance.item_stable_key)!;
        const characterStableKey = row.characterStableKey === undefined ? provenance.source_stable_key : row.characterStableKey;
        const label = labels[provenance.source_stable_key ?? ''] ?? labels[characterStableKey ?? ''];
        return [{ ...item, ...row, itemStableKey: item.itemStableKey, characterStableKey,
            sourceName: row.sourceName ?? label?.name ?? '', sourceWikiPageName: row.sourceWikiPageName === '' ? null : row.sourceWikiPageName ?? label?.wikiPageName ?? null,
            referenceNames, locationSources: labels, provenance, kind: provenance.kind,
            acquisitionKey: provenance.source_key, originatingItemStableKey: provenance.item_stable_key }];
    });
    const itemReference = (item: ReferencedItem): MiningNodeItem => ({ ...item, provenance: facts[item.provenance] });
    return { ...data, itemSources, markers: { ...data.markers,
        itemBags: data.markers.itemBags.map((marker) => ({ ...marker, provenance: facts[marker.provenance] })),
        miningNodes: data.markers.miningNodes.map((marker) => ({ ...marker, items: marker.items.map(itemReference) })),
        water: data.markers.water.map((marker) => ({ ...marker, daytimeItems: marker.daytimeItems.map(itemReference),
            nighttimeItems: marker.nighttimeItems.map(itemReference) }))
    } };
}

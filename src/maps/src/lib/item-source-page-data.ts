import type { ItemAcquisition, ProvenanceCondition, ProvenanceLocation } from './item-provenance';
import type { ItemSourceRow, MiningNodeItem } from './map-markers';
import type { MapMarkerData } from './types/world-map';

type Markers = Omit<MapMarkerData, 'zones' | 'itemSources'>;
const ROW_FIELDS = ['itemStableKey', 'displayName', 'wikiPageName', 'iconHash', 'sourceName',
    'sourceWikiPageName', 'characterStableKey', 'price', 'referenceNames', 'locationSources'] as const;
const SOURCE_FIELDS = ['item_stable_key', 'kind', 'source_stable_key', 'source_group_key', 'source_copy_stable_key',
    'mechanic', 'probability_kind', 'probability_min', 'probability_max', 'probability_basis', 'quantity_kind',
    'quantity_min', 'quantity_max', 'expected_quantity', 'guaranteed', 'place_set_key'] as const;
const PLACE_FIELDS = ['place_key', 'relation', 'scene', 'zone_stable_key', 'marker_stable_key', 'x', 'z',
    'player_level_min', 'player_level_max', 'source_copy_stable_key', 'entry_zone_line_keys'] as const;
const CONDITION_FIELDS = ['gate_index', 'alternative_index', 'atom_index', 'gate_key', 'predicate',
    'reference_stable_key', 'reference_slot', 'actor', 'value', 'minimum', 'maximum',
    'minimum_inclusive', 'maximum_inclusive', 'phase'] as const;

function encode<T>(record: T, fields: readonly (keyof T)[]): unknown[] {
    return fields.map((field) => record[field]);
}
function decode<T>(values: unknown[], fields: readonly (keyof T)[]): T {
    return Object.fromEntries(fields.map((field, index) => [field, values[index]])) as T;
}
type EncodedFact = [values: unknown[], conditions: unknown[][]];
type EncodedPlace = [values: unknown[], conditions: unknown[][]];

type ReferencedItem = Omit<MiningNodeItem, 'provenance'> & { provenance: string };
export interface SerializedItemSourcePageData {
    itemSources: unknown[][];
    itemFacts: Record<string, EncodedFact>;
    itemPlaces: Record<string, EncodedPlace[]>;
    markers: Omit<Markers, 'itemBags' | 'miningNodes' | 'water'> & {
        itemBags: (Omit<Markers['itemBags'][number], 'provenance'> & { provenance: string })[];
        miningNodes: (Omit<Markers['miningNodes'][number], 'items'> & { items: ReferencedItem[] })[];
        water: (Omit<Markers['water'][number], 'daytimeItems' | 'nighttimeItems'> & {
            daytimeItems: ReferencedItem[]; nighttimeItems: ReferencedItem[];
        })[];
    };
}
/** Store each source and place set once. Tuples avoid repeating field names in page data. */
export function serializeItemSourcePageData(rows: ItemSourceRow[], markers: Markers): SerializedItemSourcePageData {
    const itemFacts: Record<string, EncodedFact> = {};
    const itemPlaces: Record<string, EncodedPlace[]> = {};
    // The world map renders typed popup components. HTML belongs only to legacy zone pages.
    const presentationMarkers = Object.fromEntries(Object.entries(markers).map(([kind, entries]) => [
        kind, entries.map((marker) => {
            const presentation = { ...marker };
            if ('popup' in presentation) delete presentation.popup;
            return presentation;
        })
    ])) as Markers;
    function sourceKey(fact: ItemAcquisition): string {
        if (!(fact.source_key in itemFacts)) {
            itemFacts[fact.source_key] = [encode(fact, SOURCE_FIELDS), fact.conditions.map((atom) => encode(atom, CONDITION_FIELDS))];
            if (fact.place_set_key && !(fact.place_set_key in itemPlaces)) {
                itemPlaces[fact.place_set_key] = fact.locations.map((place) => [encode(place, PLACE_FIELDS),
                    place.conditions.map((atom) => encode(atom, CONDITION_FIELDS))]);
            }
        }
        return fact.source_key;
    }
    const itemSources = rows.map((row) => [sourceKey(row.provenance), ...encode(row, ROW_FIELDS)]);
    const itemReference = (item: MiningNodeItem) => ({ ...item, provenance: sourceKey(item.provenance) });
    return { itemSources, itemFacts, itemPlaces, markers: { ...presentationMarkers,
        itemBags: presentationMarkers.itemBags.map((marker) => ({ ...marker, provenance: sourceKey(marker.provenance) })),
        miningNodes: presentationMarkers.miningNodes.map((marker) => ({ ...marker, items: marker.items.map(itemReference) })),
        water: presentationMarkers.water.map((marker) => ({ ...marker, daytimeItems: marker.daytimeItems.map(itemReference),
            nighttimeItems: marker.nighttimeItems.map(itemReference) }))
    } };
}

/** Restore presentation objects once, resolving every shared place set by its key. */
export function hydrateItemSourcePageData<T extends SerializedItemSourcePageData>(data: T): Omit<T, 'itemSources' | 'markers'> & {
    itemSources: ItemSourceRow[]; markers: Markers;
} {
    const places: Record<string, ProvenanceLocation[]> = {};
    for (const [key, entries] of Object.entries(data.itemPlaces)) {
        places[key] = entries.map(([values, conditions]) => ({ ...decode<ProvenanceLocation>(values, PLACE_FIELDS),
            conditions: conditions.map((atoms) => decode<ProvenanceCondition>(atoms, CONDITION_FIELDS)) }));
    }
    const facts: Record<string, ItemAcquisition> = {};
    for (const [key, [values, conditions]] of Object.entries(data.itemFacts)) {
        const fact = decode<ItemAcquisition>(values, SOURCE_FIELDS);
        facts[key] = { ...fact, source_key: key, conditions: conditions.map((atoms) => decode<ProvenanceCondition>(atoms, CONDITION_FIELDS)),
            locations: fact.place_set_key ? places[fact.place_set_key] : [] };
    }
    const itemSources: ItemSourceRow[] = data.itemSources.map(([key, ...values]) => {
        const provenance = facts[key as string];
        return { ...decode<ItemSourceRow>(values, ROW_FIELDS), provenance, kind: provenance.kind,
            acquisitionKey: provenance.source_key, originatingItemStableKey: provenance.item_stable_key };
    });
    const itemReference = (item: Omit<MiningNodeItem, 'provenance'> & { provenance: string }): MiningNodeItem =>
        ({ ...item, provenance: facts[item.provenance] });
    return { ...data, itemSources, markers: { ...data.markers,
        itemBags: data.markers.itemBags.map((marker) => ({ ...marker, provenance: facts[marker.provenance] })),
        miningNodes: data.markers.miningNodes.map((marker) => ({ ...marker, items: marker.items.map(itemReference) })),
        water: data.markers.water.map((marker) => ({ ...marker, daytimeItems: marker.daytimeItems.map(itemReference),
            nighttimeItems: marker.nighttimeItems.map(itemReference) }))
    } };
}

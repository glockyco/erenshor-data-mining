import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { Repository } from './database.node';
import { getMapsDatabasePath } from './database-path.server';
import type { ItemDisposition, ItemProvenanceSnapshot } from './item-provenance';
import type { ItemSourceRow } from './map-markers';
import { ItemSearchProvider } from './map/search/item-source-provider';
import type { ResolvedItemSource } from './map/search/item-source-provider';

interface AcquisitionCoverage {
    source_key: string;
    originating_item_key: string;
    display_item_key: string | null;
    status: 'shown' | 'omitted';
    reason: 'map_visibility_no_unique_alias' | 'display_lifecycle_not_current' | null;
    item_search_group_key: string | null;
}

export interface MapProvenanceCoverage {
    input: ItemProvenanceSnapshot['metadata'];
    item_dispositions: ItemDisposition[];
    zone_line_destinations: ItemProvenanceSnapshot['zone_line_destinations'];
    acquisitions: AcquisitionCoverage[];
    groups: { item_stable_key: string; group_key: string; presentation: ResolvedItemSource['presentation']; source_keys: string[] }[];
}

/** Validate public source identities offline. Nothing from this manifest enters page props. */
export function buildMapProvenanceCoverage(snapshot: ItemProvenanceSnapshot, rows: ItemSourceRow[], provider: ItemSearchProvider): MapProvenanceCoverage {
    const dispositions = new Map(snapshot.dispositions.map((record) => [record.item_stable_key, record]));
    const items = new Map(snapshot.items.map((item) => [item.stable_key, item]));
    const visibleByPage = new Map<string, ItemProvenanceSnapshot['items']>();
    for (const item of snapshot.items) {
        if (!dispositions.has(item.stable_key)) throw new Error(`Missing public item disposition: ${item.stable_key}`);
        if (!item.is_map_visible || !item.wiki_page_name?.trim()) continue;
        const candidates = visibleByPage.get(item.wiki_page_name) ?? [];
        candidates.push(item);
        visibleByPage.set(item.wiki_page_name, candidates);
    }
    const acquisitions: AcquisitionCoverage[] = [];
    const expected = new Map<string, AcquisitionCoverage>();
    const identities = new Set<string>();
    for (const fact of snapshot.acquisitions) {
        if (identities.has(fact.source_key)) throw new Error(`Duplicate public source identity: ${fact.source_key}`);
        identities.add(fact.source_key);
        const original = items.get(fact.item_stable_key);
        if (!original) throw new Error(`Unresolved public source item: ${fact.source_key}`);
        const aliases = original.wiki_page_name ? visibleByPage.get(original.wiki_page_name) : undefined;
        const display = original.is_map_visible ? original : aliases?.length === 1 ? aliases[0] : null;
        const reason = !display ? 'map_visibility_no_unique_alias' :
            dispositions.get(display.stable_key)?.disposition !== 'current' ? 'display_lifecycle_not_current' : null;
        const entry: AcquisitionCoverage = {
            source_key: fact.source_key, originating_item_key: fact.item_stable_key,
            display_item_key: display?.stable_key ?? null, status: reason ? 'omitted' : 'shown', reason,
            item_search_group_key: null
        };
        acquisitions.push(entry);
        if (!reason) expected.set(fact.source_key, entry);
    }
    const shown = new Map<string, ItemSourceRow>();
    for (const row of rows) {
        if (shown.has(row.acquisitionKey)) throw new Error(`Duplicate map source identity: ${row.acquisitionKey}`);
        const entry = expected.get(row.acquisitionKey);
        if (!entry) throw new Error(`Extra map source identity: ${row.acquisitionKey}`);
        if (row.originatingItemStableKey !== entry.originating_item_key || row.itemStableKey !== entry.display_item_key) {
            throw new Error(`Map source identity mismatch: ${row.acquisitionKey}`);
        }
        shown.set(row.acquisitionKey, row);
    }
    for (const key of expected.keys()) {
        if (!shown.has(key)) throw new Error(`Missing map source identity: ${key}`);
    }
    const groups: MapProvenanceCoverage['groups'] = [];
    const searchable = new Set<string>();
    for (const { result } of provider.buildIndex()) {
        if (result.type !== 'item') continue;
        for (const source of provider.getSourcesForItem(result.itemStableKey)) {
            const key = source.row.acquisitionKey;
            const row = shown.get(key);
            if (!row || row.itemStableKey !== result.itemStableKey || source.row.itemStableKey !== row.itemStableKey ||
                source.row.originatingItemStableKey !== row.originatingItemStableKey || source.members.length !== 1 ||
                source.members[0].acquisitionKey !== key || source.members[0].itemStableKey !== row.itemStableKey ||
                source.members[0].originatingItemStableKey !== row.originatingItemStableKey) {
                throw new Error(`Invalid map search source identity: ${key}`);
            }
            if (searchable.has(key)) throw new Error(`Duplicate map search source identity: ${key}`);
            searchable.add(key);
            const groupKey = JSON.stringify([result.itemStableKey, key]);
            expected.get(key)!.item_search_group_key = groupKey;
            groups.push({ item_stable_key: result.itemStableKey, group_key: groupKey,
                presentation: source.presentation, source_keys: [key] });
        }
    }
    for (const key of expected.keys()) {
        if (!searchable.has(key)) throw new Error(`Missing map search source identity: ${key}`);
    }
    return { input: snapshot.metadata, item_dispositions: snapshot.dispositions,
        zone_line_destinations: snapshot.zone_line_destinations, acquisitions, groups };
}

export async function writeMapProvenanceManifest(outputPath: string, databasePath = getMapsDatabasePath()): Promise<void> {
    const repository = new Repository();
    try {
        await repository.init(databasePath);
        const snapshot = await repository.getItemProvenanceSnapshot();
        const rows = await repository.getItemSources();
        const provider = new ItemSearchProvider(rows, [], [], [], [], await repository.getAllItems());
        const manifest = buildMapProvenanceCoverage(snapshot, rows, provider);
        await mkdir(path.dirname(outputPath), { recursive: true });
        await writeFile(outputPath, JSON.stringify({ input_database: path.resolve(databasePath), ...manifest }, null, 2) + '\n');
    } finally {
        repository.close();
    }
}

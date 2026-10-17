import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { Repository } from './database.node';
import { getMapsDatabasePath } from './database-path.server';
import { ACQUISITION_KINDS, USE_KINDS, isActionableAcquisition, publicConditionGates, publicConditionOmissionReason } from './item-provenance';
import type { ItemAcquisition, ItemDisposition, ItemProvenanceSnapshot, ProvenanceCondition } from './item-provenance';
import type { ItemSourceRow } from './map-markers';
import { ItemSearchProvider } from './map/search/item-source-provider';
import type { ResolvedItemSource } from './map/search/item-source-provider';


interface AcquisitionCoverage {
    acquisition_key: string;
    originating_item_key: string;
    originating_disposition: ItemDisposition;
    source_row_status: string;
    item_search_status: string;
    item_search_group_key: string | null;
    public_condition_omissions: { location_key: string | null; condition: ProvenanceCondition; reason: string }[];
    fact: ItemAcquisition;
}
export interface MapProvenanceCoverage {
    input: ItemProvenanceSnapshot['metadata'];
    item_dispositions: ItemDisposition[];
    zone_line_destinations: ItemProvenanceSnapshot['zone_line_destinations'];
    acquisitions: AcquisitionCoverage[];
    item_uses: { use_key: string; originating_item_key: string; reason: string; fact: ItemProvenanceSnapshot['uses'][number] }[];
    groups: { item_stable_key: string; group_key: string; presentation: ResolvedItemSource['presentation']; members: ItemSourceRow[] }[];
}

function normalized(value: unknown): unknown {
    if (Array.isArray(value)) return value.map(normalized);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
        .map(([key, child]) => [key, normalized(child)]));
    return value;
}

function requireEqual(actual: unknown, expected: unknown, identity: string): void {
    if (actual !== expected && JSON.stringify(normalized(actual)) !== JSON.stringify(normalized(expected))) {
        throw new Error(`Map provenance dimension mismatch: ${identity}`);
    }
}

/** Validate the real adapter payload offline. Nothing from this manifest enters page props. */
export function buildMapProvenanceCoverage(snapshot: ItemProvenanceSnapshot, rows: ItemSourceRow[], provider: ItemSearchProvider): MapProvenanceCoverage {
    const dispositions = new Map(snapshot.dispositions.map((record) => [record.item_stable_key, record]));
    const items = new Map(snapshot.items.map((item) => [item.stable_key, item]));
    const visibleByPage = new Map<string, ItemProvenanceSnapshot['items']>();
    for (const item of snapshot.items) {
        if (!dispositions.has(item.stable_key)) throw new Error(`Missing canonical item disposition: ${item.stable_key}`);
        if (!item.is_map_visible || !item.wiki_page_name?.trim()) continue;
        const candidates = visibleByPage.get(item.wiki_page_name) ?? [];
        candidates.push(item);
        visibleByPage.set(item.wiki_page_name, candidates);
    }
    const factsByKey = new Map(snapshot.acquisitions.map((fact) => [fact.acquisition_key, fact]));
    const bonuses = new Map<string, ItemAcquisition[]>();
    for (const fact of snapshot.acquisitions) {
        if (fact.kind !== 'fishing_bonus' || fact.probability_stage !== 'native_pool' ||
            fact.mechanic !== 'fishing_global_replacement' || fact.probability_kind !== 'exact') continue;
        const candidates = bonuses.get(fact.item_stable_key) ?? [];
        candidates.push(fact);
        bonuses.set(fact.item_stable_key, candidates);
    }
    const rowsByAcquisition = new Map<string, ItemSourceRow>();
    for (const row of rows) {
        const fact = factsByKey.get(row.acquisitionKey);
        if (!fact || rowsByAcquisition.has(row.acquisitionKey) || row.originatingItemStableKey !== fact.item_stable_key || row.kind !== fact.kind) {
            throw new Error(`Map provenance origin mismatch: ${row.acquisitionKey}`);
        }
        requireEqual(row.provenance, fact, fact.acquisition_key);
        requireEqual(row.originatingDisposition, dispositions.get(fact.item_stable_key), `${fact.acquisition_key}:origin_lifecycle`);
        requireEqual(row.displayDisposition, dispositions.get(row.itemStableKey), `${fact.acquisition_key}:display_lifecycle`);
        const bonus = fact.kind === 'fishing' && fact.probability_kind === 'exact'
            ? bonuses.get(fact.item_stable_key)?.find((candidate) => candidate.probability_min === fact.probability_min &&
                candidate.probability_max === fact.probability_max) ?? null : null;
        requireEqual(row.fishingBonus, bonus, `${fact.acquisition_key}:fishing_bonus`);
        rowsByAcquisition.set(row.acquisitionKey, row);
    }
    const groups: MapProvenanceCoverage['groups'] = [];
    const groupByAcquisition = new Map<string, string>();
    const presentationByAcquisition = new Map<string, ResolvedItemSource['presentation']>();
    const globalGroups = new Set<string>();
    for (const { result } of provider.buildIndex()) {
        if (result.type !== 'item') continue;
        for (const source of provider.getSourcesForItem(result.itemStableKey)) {
            const groupKey = JSON.stringify([result.itemStableKey, source.row.acquisitionKey]);
            for (const member of source.members) {
                const row = rowsByAcquisition.get(member.acquisitionKey);
                if (!row || groupByAcquisition.has(member.acquisitionKey) || member.itemStableKey !== result.itemStableKey) {
                    throw new Error(`Invalid map coverage group member: ${member.acquisitionKey}`);
                }
                requireEqual(member, row, `${member.acquisitionKey}:group_member`);
                if ((source.presentation === 'any_water') !== (row.fishingBonus !== null)) {
                    throw new Error(`Incorrect global fishing presentation: ${member.acquisitionKey}`);
                }
                groupByAcquisition.set(member.acquisitionKey, groupKey);
                presentationByAcquisition.set(member.acquisitionKey, source.presentation);
            }
            if (source.presentation === 'any_water') {
                if (!source.members.length || source.markers.length || source.entries.length || source.unlocated.length) {
                    throw new Error(`Any water source exposes locations: ${groupKey}`);
                }
                const bonusKey = source.members[0].fishingBonus!.acquisition_key;
                const identity = JSON.stringify([result.itemStableKey, bonusKey]);
                if (globalGroups.has(identity) || source.members.some((member) => member.fishingBonus?.acquisition_key !== bonusKey)) {
                    throw new Error(`Duplicate or mixed Any water source: ${groupKey}`);
                }
                globalGroups.add(identity);
            } else if (source.members.length !== 1) throw new Error(`Unexpected map source grouping: ${groupKey}`);
            groups.push({ item_stable_key: result.itemStableKey, group_key: groupKey, presentation: source.presentation, members: source.members });
        }
    }
    const acquisitions: AcquisitionCoverage[] = [];
    for (const fact of snapshot.acquisitions) {
        if (!Object.hasOwn(ACQUISITION_KINDS, fact.kind)) throw new Error(`Unsupported canonical map acquisition kind: ${fact.kind}`);
        const original = items.get(fact.item_stable_key);
        const lifecycle = dispositions.get(fact.item_stable_key);
        if (!original || !lifecycle) throw new Error(`Unresolved canonical acquisition item: ${fact.acquisition_key}`);
        const aliases = original.wiki_page_name ? visibleByPage.get(original.wiki_page_name) : undefined;
        const display = original.is_map_visible ? original : aliases?.length === 1 ? aliases[0] : null;
        let reason: string | null = lifecycle.disposition !== 'current' ? `lifecycle_${lifecycle.disposition}` :
            fact.player_access_state !== 'verified_player' ? `access_${fact.player_access_state}` :
                fact.probability_stage !== 'final_acquisition' ? 'native_pool_evidence' :
                    fact.probability_max !== null && fact.probability_max <= 0 ? 'zero_probability' :
                        !isActionableAcquisition(fact) ? 'unsatisfiable_conditions' :
                            !display ? 'map_visibility_no_unique_alias' :
                                dispositions.get(display.stable_key)?.disposition !== 'current' ? 'display_lifecycle_not_current' : null;
        const row = rowsByAcquisition.get(fact.acquisition_key);
        if ((reason === null) !== Boolean(row)) throw new Error(`Map source coverage mismatch: ${fact.acquisition_key}`);
        if (row && row.itemStableKey !== display?.stable_key) throw new Error(`Map display alias mismatch: ${fact.acquisition_key}`);
        const group = groupByAcquisition.get(fact.acquisition_key) ?? null;
        const shouldBeSearchable = reason === null && Boolean(display?.wiki_page_name?.trim());
        if (shouldBeSearchable !== Boolean(group)) throw new Error(`Map item-search coverage mismatch: ${fact.acquisition_key}`);
        const sourceRowStatus = reason ?? 'preserved';
        if (reason === null && !shouldBeSearchable) reason = 'item_search_requires_wiki_page';
        const conditionOmissions: AcquisitionCoverage['public_condition_omissions'] = [];
        const conditionGroups = [
            { conditions: fact.conditions, location_key: null },
            ...fact.locations.map((location) => ({ conditions: location.conditions, location_key: location.location_key }))
        ];
        for (const entry of conditionGroups) {
            const visible = new Set(publicConditionGates(entry.conditions).flatMap((gate) => gate.alternatives.flat()));
            for (const condition of entry.conditions) {
                const omission = publicConditionOmissionReason(condition) ??
                    (!visible.has(condition) ? 'gate_has_private_alternative' :
                        presentationByAcquisition.get(fact.acquisition_key) === 'any_water'
                            ? condition.predicate === 'time_of_day' ? 'grouped_global_fishing_time' : 'grouped_global_fishing_member_condition'
                            : null);
                if (omission) conditionOmissions.push({ condition, location_key: entry.location_key, reason: omission });
            }
        }
        acquisitions.push({ acquisition_key: fact.acquisition_key, originating_item_key: fact.item_stable_key,
            originating_disposition: lifecycle, source_row_status: sourceRowStatus,
            item_search_status: reason ?? 'preserved', item_search_group_key: group, public_condition_omissions: conditionOmissions, fact });
    }
    const itemUses = snapshot.uses.map((fact) => {
        if (!Object.hasOwn(USE_KINDS, fact.kind) || !items.has(fact.item_stable_key) || !dispositions.has(fact.item_stable_key)) {
            throw new Error(`Unsupported or unresolved canonical map use: ${fact.use_key}`);
        }
        return { use_key: fact.use_key, originating_item_key: fact.item_stable_key,
            reason: 'map_has_no_item_use_listing', fact };
    });
    return { input: snapshot.metadata, item_dispositions: snapshot.dispositions,
        zone_line_destinations: snapshot.zone_line_destinations, acquisitions, item_uses: itemUses, groups };
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

import type { Database, SqlValue } from 'sql.js/dist/sql-wasm.js';

export const STORED_RETURN_LABEL = 'Return to where you teleported from';

export interface ZoneLineDestinationContext {
    zone_line_stable_key: string;
    kind: 'stored_return';
    destination_state_key: string;
    landing_state_key: string;
    source_key: string;
}

export interface ZoneLineDestinationSnapshot {
    zone_line_stable_key: string;
    scene: string | null;
    zoning_capable: boolean;
    has_physical_location: boolean;
    serialized_default: {
        destination_zone_stable_key: string | null;
        destination_scene: string | null;
        landing_position: { x: number | null; y: number | null; z: number | null };
    };
    context: ZoneLineDestinationContext | null;
}

export function readZoneLineDestinationContexts(db: Database): Map<string, ZoneLineDestinationContext> {
    const statement = db.prepare(`SELECT context.*, native.stable_key AS native_key
        FROM zone_line_destination_contexts context
        LEFT JOIN zone_lines native ON native.stable_key = context.zone_line_stable_key
        ORDER BY context.zone_line_stable_key`);
    const contexts = new Map<string, ZoneLineDestinationContext>();
    try {
        while (statement.step()) {
            const { native_key, ...row } = statement.getAsObject();
            if (Object.keys(row).sort().join(',') !== 'destination_state_key,kind,landing_state_key,source_key,zone_line_stable_key' ||
                row.kind !== 'stored_return' || typeof native_key !== 'string' ||
                ['zone_line_stable_key', 'destination_state_key', 'landing_state_key', 'source_key']
                    .some((key) => typeof row[key] !== 'string' || !row[key])) {
                throw new Error('Invalid common zone-line destination context');
            }
            const key = row.zone_line_stable_key as string;
            if (contexts.has(key)) throw new Error(`Duplicate zone-line destination context: ${key}`);
            contexts.set(key, row as unknown as ZoneLineDestinationContext);
        }
    } finally {
        statement.free();
    }
    return contexts;
}

export function readZoneLineDestinationSnapshot(
    db: Database, contexts: ReadonlyMap<string, ZoneLineDestinationContext>
): ZoneLineDestinationSnapshot[] {
    const statement = db.prepare(`SELECT native.stable_key, native.scene, native.x, native.y, native.z,
        native.destination_zone_stable_key, destination.scene_name AS destination_scene,
        native.landing_position_x, native.landing_position_y, native.landing_position_z,
        capable.stable_key AS capability_key
        FROM zone_lines native
        LEFT JOIN zones destination ON destination.stable_key = native.destination_zone_stable_key
        LEFT JOIN zone_lines_with_zoning_capability capable ON capable.stable_key = native.stable_key
        ORDER BY native.stable_key`);
    const snapshots: ZoneLineDestinationSnapshot[] = [];
    try {
        while (statement.step()) {
            const row = statement.getAsObject();
            const coordinates: SqlValue[] = [row.x, row.y, row.z];
            const key = row.stable_key as string;
            snapshots.push({ zone_line_stable_key: key, scene: row.scene as string | null,
                zoning_capable: row.capability_key !== null,
                has_physical_location: typeof row.scene === 'string' && Boolean(row.scene) &&
                    coordinates.every((coordinate) => typeof coordinate === 'number' && Number.isFinite(coordinate)),
                serialized_default: {
                    destination_zone_stable_key: row.destination_zone_stable_key as string | null,
                    destination_scene: row.destination_scene as string | null,
                    landing_position: { x: row.landing_position_x as number | null,
                        y: row.landing_position_y as number | null, z: row.landing_position_z as number | null }
                }, context: contexts.get(key) ?? null });
        }
    } finally {
        statement.free();
    }
    return snapshots;
}

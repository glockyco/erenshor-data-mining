import type { ZoneWorldPosition } from '../../types/world-map';
import type { PositionOverrides } from './persistence';

export interface ZonePositionExport {
    zoneKey: string;
    worldX: number;
    worldY: number;
}

export function exportToJson(
    overrides: PositionOverrides,
    zones: ZoneWorldPosition[]
): ZonePositionExport[] {
    return zones.map((zone) => {
        const override = overrides[zone.key];
        return {
            zoneKey: zone.key,
            worldX: override?.worldX ?? zone.worldX,
            worldY: override?.worldY ?? zone.worldY
        };
    });
}

export async function copyToClipboard(data: ZonePositionExport[]): Promise<void> {
    const json = JSON.stringify(data, null, 2);
    await navigator.clipboard.writeText(json);
}

export function downloadJson(data: ZonePositionExport[]): void {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'zone-positions.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

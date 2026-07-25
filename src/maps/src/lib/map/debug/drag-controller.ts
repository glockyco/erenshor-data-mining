import type { ZoneWorldPosition } from '../../types/world-map';

type DragState = 'idle' | 'dragging';

export interface DragInfo {
    layer?: { id: string };
    object?: ZoneWorldPosition;
    coordinate: [number, number];
}

export class DragController {
    private state: DragState = 'idle';
    private zoneKey: string | null = null;
    private startWorldPos: [number, number] | null = null;
    private originalOffset: { worldX: number; worldY: number } | null = null;

    constructor(
        private onDragUpdate: (
            zoneKey: string,
            newOffset: { worldX: number; worldY: number }
        ) => void,
        private onDragEnd: () => void
    ) {}

    get isDragging(): boolean {
        return this.state === 'dragging';
    }

    get draggingZoneKey(): string | null {
        return this.zoneKey;
    }

    tryStartDrag(info: DragInfo, shiftKey: boolean): boolean {
        if (!shiftKey) return false;
        if (info.layer?.id !== 'zone-bounds' || !info.object) return false;

        this.state = 'dragging';
        this.zoneKey = info.object.key;
        this.startWorldPos = info.coordinate;
        this.originalOffset = {
            worldX: info.object.worldX,
            worldY: info.object.worldY
        };

        return true;
    }

    handleDrag(coordinate: [number, number], shiftKey: boolean): boolean {
        if (this.state !== 'dragging') return false;

        if (!shiftKey) {
            this.cancel();
            return false;
        }

        if (!this.startWorldPos || !this.originalOffset || !this.zoneKey) {
            return false;
        }

        const deltaX = coordinate[0] - this.startWorldPos[0];
        const deltaY = coordinate[1] - this.startWorldPos[1];

        this.onDragUpdate(this.zoneKey, {
            worldX: this.originalOffset.worldX + deltaX,
            worldY: this.originalOffset.worldY + deltaY
        });

        return true;
    }

    handleDragEnd(): void {
        if (this.state === 'dragging') {
            this.onDragEnd();
        }
        this.reset();
    }

    cancel(): void {
        this.reset();
    }

    private reset(): void {
        this.state = 'idle';
        this.zoneKey = null;
        this.startWorldPos = null;
        this.originalOffset = null;
    }
}

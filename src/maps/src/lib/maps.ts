import zoneCaptureConfig from './data/zone-capture-config.json';

export interface MapConfig {
    zoneName: string;
    tileUrl: string;
    baseTilesX: number;
    baseTilesY: number;
    tileSize: number;
    zoom: number;
    minZoom: number;
    maxZoom: number;
    originX: number;
    originY: number;
}

/** Display names keyed by zone key. The capture config only has sceneName (== key). */
const DISPLAY_NAMES: Record<string, string> = {
    Abyssal: 'Abyssal Lake',
    Azure: 'Port Azure',
    Azynthi: "Azynthi's Garden (Dimensional Rift)",
    AzynthiClear: "Azynthi's Garden",
    Blight: 'The Blight',
    BloomingSepulcher: 'Blooming Sepulcher',
    Bonepits: 'The Bonepits',
    Brake: "Faerie's Brake",
    Braxonia: 'Fallen Braxonia',
    Braxonian: 'Braxonian Desert',
    Duskenlight: 'The Duskenlight Coast',
    DuskenPortal: 'Mysterious Portal (The Duskenlight Coast)',
    Elderstone: 'The Elderstone Mines',
    FernallaField: "Fernalla's Revival Plains",
    FernallaPortal: "Mysterious Portal (Fernalla's Revival Plains)",
    Hidden: 'Hidden Hills',
    Jaws: 'Jaws of Sivakaya',
    Krakengard: 'Old Krakengard',
    Loomingwood: 'Loomingwood Forest',
    Malaroth: "Malaroth's Nesting Grounds",
    PrielPlateau: 'Prielian Cascade',
    Ripper: "Ripper's Keep",
    RipperPortal: "Mysterious Portal (Ripper's Keep)",
    Rockshade: 'Rockshade Hold',
    Rottenfoot: 'Rottenfoot',
    SaltedStrand: 'Blacksalt Strand',
    Silkengrass: 'Silkengrass Meadowlands',
    Soluna: "Soluna's Landing",
    Stowaway: "Stowaway's Step",
    ShiveringStep: 'Shivering Step',
    SummerEvent: 'Bellwain Island',
    Tutorial: 'Island Tomb',
    Undercity: 'Lost Cellar',
    Underspine: 'Underspine Hollow',
    Vitheo: "Vitheo's Watch",
    VitheosEnd: "Vitheo's Rest",
    Windwashed: 'Windwashed Pass',
    Willowwatch: 'Willowwatch Ridge'
};

function computeMinZoom(baseTilesX: number, baseTilesY: number): number {
    const maxDim = Math.max(baseTilesX, baseTilesY);
    return maxDim <= 1 ? 0 : -Math.ceil(Math.log2(maxDim));
}

type ZoneCaptureEntry = {
    sceneName: string;
    baseTilesX: number;
    baseTilesY: number;
    tileSize: number;
    maxZoom: number;
    originX: number;
    originY: number;
    northBearing: number | null;
    captureVariants: string[];
    cropRect: unknown;
    exclusionRules: unknown[];
};

const config = zoneCaptureConfig as Record<string, ZoneCaptureEntry>;

export const MAPS: Record<string, MapConfig> = Object.fromEntries(
    Object.entries(config)
        .filter(([key]) => key in DISPLAY_NAMES)
        .map(([key, zone]) => [
            key,
            {
                zoneName: DISPLAY_NAMES[key],
                tileUrl: `/tiles/${key}/{z}/{x}/{y}.webp`,
                baseTilesX: zone.baseTilesX,
                baseTilesY: zone.baseTilesY,
                tileSize: zone.tileSize,
                zoom: 0,
                minZoom: computeMinZoom(zone.baseTilesX, zone.baseTilesY),
                maxZoom: zone.maxZoom,
                originX: zone.originX,
                originY: zone.originY
            } satisfies MapConfig
        ])
);

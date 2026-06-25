export type ScaleBarState = {
    units: number;
    widthPx: number;
    label: string;
};

type ScaleBarOptions = {
    measuredUnits: number;
    maxWidthPx: number;
};

const NICE_FACTORS = [1, 2, 2.5, 5] as const;

export function computeScaleBarState({
    measuredUnits,
    maxWidthPx
}: ScaleBarOptions): ScaleBarState | null {
    if (!Number.isFinite(measuredUnits) || !Number.isFinite(maxWidthPx)) return null;
    if (measuredUnits <= 0 || maxWidthPx <= 0) return null;

    const units = chooseNiceDistance(measuredUnits);
    if (units == null) return null;

    const unitsPerPixel = measuredUnits / maxWidthPx;
    const widthPx = roundToHundredths(units / unitsPerPixel);
    if (!Number.isFinite(widthPx) || widthPx <= 0) return null;

    return {
        units,
        widthPx,
        label: formatScaleLabel(units)
    };
}

export function formatScaleLabel(units: number): string {
    return `${formatNumber(units)} units`;
}

function chooseNiceDistance(maxUnits: number): number | null {
    if (!Number.isFinite(maxUnits) || maxUnits <= 0) return null;

    const exponent = Math.floor(Math.log10(maxUnits));

    for (let power = exponent; power >= exponent - 1; power -= 1) {
        const magnitude = 10 ** power;
        for (let i = NICE_FACTORS.length - 1; i >= 0; i -= 1) {
            const candidate = NICE_FACTORS[i] * magnitude;
            if (candidate <= maxUnits) return normalizeDistance(candidate);
        }
    }

    return null;
}

function normalizeDistance(value: number): number {
    return Number(value.toPrecision(12));
}

function roundToHundredths(value: number): number {
    return Math.round(value * 100) / 100;
}

function formatNumber(value: number): string {
    if (value >= 1000) {
        return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value);
    }
    return Number.isInteger(value) ? String(value) : String(value).replace(/0+$/, '').replace(/\.$/, '');
}

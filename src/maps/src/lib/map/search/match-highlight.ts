export type TextSegment = {
    text: string;
    highlighted: boolean;
};

/**
 * Split a display name into highlighted/unhighlighted segments based on a
 * match range. Returns a single unhighlighted segment when range is null
 * (fuzzy matches — no highlight).
 */
export function splitByMatchRange(
    name: string,
    range: [number, number] | null
): TextSegment[] {
    if (range === null) {
        return [{ text: name, highlighted: false }];
    }

    const [start, end] = range;
    const segments: TextSegment[] = [];

    if (start > 0) {
        segments.push({ text: name.slice(0, start), highlighted: false });
    }
    segments.push({ text: name.slice(start, end), highlighted: true });
    if (end < name.length) {
        segments.push({ text: name.slice(end), highlighted: false });
    }

    return segments;
}

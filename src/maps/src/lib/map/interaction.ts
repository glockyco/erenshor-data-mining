import type { DeckProps } from '@deck.gl/core';

/**
 * deck.gl's click recognizer waits out the double-click window before it
 * reports a single click, which delays every marker popup by about 300 ms. A
 * 1 ms interval reports the click at once. Double-click still zooms, and its
 * first click now also selects. The Ancient Kingdoms and Afallon maps use the
 * same setting.
 */
export const MAP_EVENT_RECOGNIZER_OPTIONS = {
    click: { interval: 1 }
} satisfies NonNullable<DeckProps['eventRecognizerOptions']>;

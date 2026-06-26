/**
 * Landing-page FAQ content.
 *
 * Single source of truth for both the rendered FAQ (FaqSection renders each
 * answer segment as text or an anchor) and the FAQPage JSON-LD (answerText
 * flattens the segments to plain text). Answers are answer-first and link to the
 * relevant tool or source so visitors are never left hanging.
 */

/** A run of answer text, or a link with display text and an href. */
export type AnswerSegment = string | { text: string; href: string; external?: boolean };

export interface FaqItem {
    question: string;
    answer: AnswerSegment[];
}

export const FAQ_ITEMS: FaqItem[] = [
    {
        question: 'Where do I find a specific enemy, NPC, or vendor?',
        answer: [
            'Search the ',
            { text: 'world map', href: '/map' },
            ' by name. It shows every spawn with its exact coordinates and spawn chance, along with vendors, resource and fishing nodes, treasure, and zone exits. Run the ',
            { text: 'companion mod', href: '/mod' },
            ' to add a live view that places your character, your party, and nearby creatures on the map as you play.'
        ]
    },
    {
        question: 'How do I see what an enemy drops?',
        answer: [
            'Click a spawn point on the ',
            { text: 'world map', href: '/map' },
            ' to open its popup. The popup lists the creatures that spawn there and their full drop tables with exact percentages, taken straight from the game files and refreshed every patch.'
        ]
    },
    {
        question: 'I cannot find an enemy that should be here. Where is it?',
        answer: [
            'It is probably on its respawn timer or away on a patrol route. The ',
            { text: 'world map', href: '/map' },
            ' shows respawn timers and patrol paths for each spawn, and the ',
            { text: 'companion mod', href: '/mod' },
            ' adds live markers so you can see exactly where everything is right now.'
        ]
    },
    {
        question: 'Do I need to install anything to use this?',
        answer: [
            'No. The ',
            { text: 'world map', href: '/map' },
            ' and the rest of the site run in your browser with nothing installed. The optional ',
            { text: 'companion mod', href: '/mod' },
            ' adds the live view, and the ',
            { text: 'Adventure Guide', href: '/adventure-guide' },
            ' adds in-game quest guidance.'
        ]
    },
    {
        question: 'Does Erenshor have a map and quest markers?',
        answer: [
            'Yes. Erenshor has a world map, a minimap, and optional quest markers. This site adds a ',
            { text: 'searchable map', href: '/map' },
            ' of every enemy, vendor, resource node, and treasure location, and the ',
            { text: 'Adventure Guide', href: '/adventure-guide' },
            ' adds full step-by-step quest routing on top of the in-game markers.'
        ]
    },
    {
        question: 'Is Erenshor multiplayer?',
        answer: [
            'No. Erenshor is an offline single-player simulated MMORPG where the other adventurers are AI SimPlayers. There is no official multiplayer. If you want to play together, the community ',
            {
                text: 'co-op mod',
                href: 'https://thunderstore.io/c/erenshor/p/mizuki/Erenshor_COOP/',
                external: true
            },
            ' brings co-op to the game.'
        ]
    },
    {
        question: 'Are SimPlayers real players or AI chatbots?',
        answer: [
            'Neither. ',
            {
                text: 'SimPlayers',
                href: 'https://erenshor.wiki.gg/wiki/Simulated_Players',
                external: true
            },
            ' are scripted AI characters (state machines and decision trees, not an LLM) that level up, group, trade, and chat to make the world feel populated.'
        ]
    },
    {
        question: 'How is this different from the official wiki?',
        answer: [
            'They work together and link to each other. The ',
            { text: 'official wiki', href: 'https://erenshor.wiki.gg', external: true },
            ' has drop rates, stats, and lore, and its enemy pages link to this map. The ',
            { text: 'world map', href: '/map' },
            ' shows you visually where everything is, with every spawn on one map, filtering, and live positions, and links back to the wiki for the deeper details.'
        ]
    }
];

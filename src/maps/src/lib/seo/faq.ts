/**
 * Landing-page FAQ content.
 *
 * Single source of truth for both the rendered FAQ (FaqSection renders each
 * answer segment as text or an anchor) and the FAQPage JSON-LD (the landing
 * page flattens the segments to plain text). Answers are answer-first and link
 * to the relevant tool or source so visitors are never left hanging.
 *
 * Items are ordered by category and FaqSection renders them as two grouped
 * clusters (tools first, then game). The JSON-LD builder reads only question
 * and answer, so `category` carries no SEO weight.
 */

/** A run of answer text, or a link with display text and an href. */
export type AnswerSegment = string | { text: string; href: string };

/** Which rendered cluster a question belongs to. */
export type FaqCategory = 'tools' | 'game';

export interface FaqItem {
    question: string;
    answer: AnswerSegment[];
    category: FaqCategory;
}

export const FAQ_ITEMS: FaqItem[] = [
    {
        question: 'Where do I find a specific enemy, NPC, or vendor?',
        category: 'tools',
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
        category: 'tools',
        answer: [
            'Click a spawn point on the ',
            { text: 'world map', href: '/map' },
            ' to open its popup. The popup lists the creatures that spawn there and their full drop tables with exact percentages, taken straight from the game files and refreshed every patch.'
        ]
    },
    {
        question: 'I cannot find an enemy that should be here. Where is it?',
        category: 'tools',
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
        category: 'tools',
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
        question: 'What mods are available for Erenshor?',
        category: 'tools',
        answer: [
            'There are two main places to get Erenshor mods. ',
            { text: 'Thunderstore', href: 'https://thunderstore.io/c/erenshor/' },
            ' is the established, legacy ecosystem for BepInEx mods. ',
            { text: 'Erenshor Vault', href: 'https://erenshorvault.app/' },
            ' and ',
            { text: 'Lunaris', href: 'https://github.com/MizukiBelhi/Lunaris' },
            ' are a mod hosting site and mod loader built by the Erenshor community to offer a more seamless modding experience. The ',
            { text: 'Adventure Guide', href: '/adventure-guide' },
            ' mod for quest walkthroughs and GPS routing, and the ',
            { text: 'Interactive Map Companion', href: '/mod' },
            ' mod for live tracking on the world map are available on both platforms.'
        ]
    },
    {
        question: 'How is this different from the official wiki?',
        category: 'tools',
        answer: [
            'They work together and link to each other. The ',
            { text: 'official wiki', href: 'https://erenshor.wiki.gg' },
            ' has drop rates, stats, and lore, and its enemy pages link to this map. The ',
            { text: 'world map', href: '/map' },
            ' shows you visually where everything is, with every spawn on one map, filtering, and live positions, and links back to the wiki for the deeper details.'
        ]
    },
    {
        question: 'Does Erenshor have a map and quest markers?',
        category: 'game',
        answer: [
            'Yes. Erenshor has a world map, a minimap, and optional quest markers. This site adds a ',
            { text: 'searchable map', href: '/map' },
            ' of every enemy, vendor, resource node, and treasure location, and the ',
            { text: 'Adventure Guide', href: '/adventure-guide' },
            ' adds full step-by-step quest routing on top of the in-game markers.'
        ]
    },
    {
        question: 'What zones are in Erenshor, and where can I find their maps?',
        category: 'game',
        answer: [
            "Browse the official wiki's ",
            {
                text: 'Zones index',
                href: 'https://erenshor.wiki.gg/wiki/Zones'
            },
            " for Erenshor's outdoor zones, dungeons, raids, and event zones. Use the ",
            { text: 'zone maps', href: '/zone-maps' },
            ' for individual area maps, or the ',
            { text: 'interactive world map', href: '/map' },
            ' to inspect zone layouts, exits, enemies, NPCs, vendors, resources, and points of interest.'
        ]
    },
    {
        question: 'What are Treasure Maps used for in Erenshor?',
        category: 'game',
        answer: [
            'A ',
            {
                text: 'Treasure Map',
                href: 'https://erenshor.wiki.gg/wiki/Treasure_Map'
            },
            ' is consumed when you right-click it to start a treasure hunt. The hunt randomly selects one of up to nine eligible zones, with the available pool determined by your current level. Enter that zone to reveal the exact coordinates, then dig up the chest and defeat its level-scaled guardians. Only one hunt can be active: starting another overwrites it, and failing the event loses the treasure. If you have more maps than you want to hunt, you can instead complete the repeatable Maps for Prichard quest: ',
            {
                text: 'Prichard Zemoro',
                href: 'https://erenshor.wiki.gg/wiki/Prichard_Zemoro'
            },
            ' takes one Treasure Map plus one Elixir of Enlightenment II and rewards one Sivakrux. See the ',
            {
                text: 'Treasure Hunting guide',
                href: 'https://erenshor.wiki.gg/wiki/Treasure_Hunting'
            },
            ' for zone pools and loot, or enable ',
            { text: 'Treasure Locations', href: '/map' },
            ' on the interactive world map to see every possible site.'
        ]
    },
    {
        question: 'What are Treasure Map pieces for?',
        category: 'game',
        answer: [
            'Collect one of each Torn Treasure Map piece: Top Left, Top Right, Bottom Left, and Bottom Right. Give all four to ',
            {
                text: 'Cecil Threbb',
                href: 'https://erenshor.wiki.gg/wiki/Cecil_Threbb'
            },
            " in Faerie's Brake to complete the repeatable ",
            {
                text: 'Repairing Treasure Maps',
                href: 'https://erenshor.wiki.gg/wiki/Repairing_Treasure_Maps'
            },
            ' quest and receive one usable ',
            {
                text: 'Treasure Map',
                href: 'https://erenshor.wiki.gg/wiki/Treasure_Map'
            },
            '. Map pieces can appear as global enemy drops and fishing catches.'
        ]
    },
    {
        question: 'Is Erenshor multiplayer?',
        category: 'game',
        answer: [
            'No. Erenshor is an offline single-player simulated MMORPG where the other adventurers are AI SimPlayers. There is no official multiplayer. If you want to play together, the community ',
            {
                text: 'co-op mod',
                href: 'https://thunderstore.io/c/erenshor/p/mizuki/Erenshor_COOP/'
            },
            ' brings co-op to the game.'
        ]
    },
    {
        question: 'Are SimPlayers real players or AI chatbots?',
        category: 'game',
        answer: [
            'Neither. ',
            {
                text: 'SimPlayers',
                href: 'https://erenshor.wiki.gg/wiki/Simulated_Players'
            },
            ' are scripted AI characters (state machines and decision trees, not an LLM) that level up, group, trade, and chat to make the world feel populated.'
        ]
    }
];

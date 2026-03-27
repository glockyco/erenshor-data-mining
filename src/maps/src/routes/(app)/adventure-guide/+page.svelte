<svelte:head>
    <title>Adventure Guide - Erenshor</title>
</svelte:head>

<!-- Hero -->
<div class="text-center mb-12">
    <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">Adventure Guide</h2>
    <div class="w-24 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
    <p class="text-slate-300 mt-4 text-lg">Every quest. Every item source. Click and go.</p>
    <p class="text-slate-400 mt-2 max-w-2xl mx-auto">
        In-game quest companion for Erenshor. 170+ quests with step-by-step walkthroughs, GPS
        navigation, and floating world markers above every quest-relevant NPC.
    </p>
    <a
        href="/mods/AdventureGuide.dll"
        class="inline-block mt-6 px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-300"
        download
    >
        <svg class="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            ></path>
        </svg>
        Download
    </a>
</div>

<div class="max-w-4xl mx-auto space-y-16">
    <!-- Navigate to anything -->
    <section>
        <h3 class="text-2xl font-bold text-white mb-4">Navigate to anything</h3>
        <img
            src="/adventure-guide-window.webp"
            alt="Quest window with walkthroughs and navigation buttons"
            class="rounded-xl border border-slate-700 mb-6 w-full"
            width="1868"
            height="1404"
            loading="lazy"
        />
        <div class="text-slate-300 space-y-3">
            <p>
                Every quest step has a <span class="font-semibold text-white">[NAV]</span> button. Click
                it and a directional arrow points you to your target — across zone boundaries, chaining
                through multiple connections to get you there.
            </p>
            <p>
                Need an item? Every source is listed — enemy drops, vendors, mining nodes, fishing
                spots, crafting recipes, quest rewards. Click any source and the arrow takes you to
                it. When a source is another quest's reward, that quest's walkthrough unfolds inline
                with its own nav buttons.
            </p>
        </div>
    </section>

    <!-- See what you've been missing -->
    <section>
        <h3 class="text-2xl font-bold text-white mb-4">See what you've been missing</h3>
        <img
            src="/adventure-guide-markers.webp"
            alt="World markers above NPCs showing quest state and respawn timers"
            class="rounded-xl border border-slate-700 mb-6 w-full"
            width="2058"
            height="600"
            loading="lazy"
        />
        <div class="text-slate-300 space-y-3">
            <p>
                Floating icons appear above NPCs in the game world — quest givers you've walked
                past, turn-in targets waiting for your items, enemies you need to hunt down. Kill a
                quest mob and its marker switches to a live respawn countdown. Night-only spawns
                show the spawn window and current game time so you know when to come back.
            </p>
        </div>
    </section>

    <!-- Know the whole path -->
    <section>
        <h3 class="text-2xl font-bold text-white mb-4">Know the whole path</h3>
        <img
            src="/adventure-guide-nav.webp"
            alt="Navigation arrow and ground path guiding to target"
            class="rounded-xl border border-slate-700 mb-6 w-full"
            width="1552"
            height="1086"
            loading="lazy"
        />
        <div class="text-slate-300 space-y-3">
            <p>
                Each step tells you who to talk to, what to say, where to go, and what items to
                collect. Level estimates on quests and steps show what you're ready for and help you
                tackle things in the right order. Come back after a week and your progress, item
                counts, and active step are right where you left them.
            </p>
        </div>
    </section>

    <!-- Download & Install -->
    <section class="bg-slate-800 rounded-xl p-8 border border-slate-700">
        <h3 class="text-2xl font-bold text-white mb-6">Install</h3>

        <p class="text-slate-300 text-sm mb-6">
            Requires <a
                href="https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/"
                class="text-purple-400 hover:text-purple-300 underline">BepInEx 5</a
            >.
        </p>

        <div class="space-y-6">
            <div>
                <h4 class="text-lg font-semibold text-white mb-2">Thunderstore install</h4>
                <p class="text-slate-300 text-sm">
                    Install from the
                    <a
                        href="https://thunderstore.io/c/erenshor/p/WoW_Much/AdventureGuide/"
                        class="text-purple-400 hover:text-purple-300 underline">Thunderstore page</a
                    >
                    with a mod manager.
                </p>
            </div>

            <div>
                <h4 class="text-lg font-semibold text-white mb-2">Manual install</h4>
                <div class="text-slate-300 text-sm space-y-2">
                    <p>
                        <a
                            href="/mods/AdventureGuide.dll"
                            class="text-purple-400 hover:text-purple-300 underline"
                            download>Download</a
                        >
                        <code class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200"
                            >AdventureGuide.dll</code
                        >
                        and place it in
                        <code class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200"
                            >BepInEx/plugins/</code
                        >.
                    </p>
                    <pre
                        class="bg-slate-900 px-3 py-2 rounded text-xs text-slate-200 overflow-x-auto mt-2"><code
                            >Erenshor/
└── BepInEx/
    └── plugins/
        └── AdventureGuide.dll</code
                        ></pre>
                </div>
            </div>
        </div>

        <div class="mt-8 pt-6 border-t border-slate-700">
            <h4 class="text-lg font-semibold text-white mb-2">Keyboard shortcuts</h4>
            <div class="text-slate-300 text-sm space-y-1">
                <p>
                    <kbd class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200 font-mono"
                        >L</kbd
                    >
                    Open the Adventure Guide
                </p>
                <p>
                    <kbd class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200 font-mono"
                        >K</kbd
                    >
                    Open the quest tracker
                </p>
                <p>
                    <kbd class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200 font-mono"
                        >P</kbd
                    >
                    Toggle ground path overlay
                </p>
            </div>
        </div>

        <div class="mt-6 pt-6 border-t border-slate-700">
            <h4 class="text-lg font-semibold text-white mb-3">Configuration</h4>
            <p class="text-slate-300 text-sm mb-4">
                Config file:
                <code class="bg-slate-900 px-1.5 py-0.5 rounded text-xs text-slate-200"
                    >BepInEx/config/wow-much.adventure-guide.cfg</code
                >
                (generated on first launch).<br />Or edit in-game with
                <a
                    href="https://github.com/BepInEx/BepInEx.ConfigurationManager"
                    class="text-purple-400 hover:text-purple-300 underline">Configuration Manager</a
                > (F1).
            </p>
            <div class="overflow-x-auto">
                <table class="w-full text-sm text-left">
                    <thead>
                        <tr class="text-slate-400 border-b border-slate-700">
                            <th class="py-2 pr-4">Setting</th>
                            <th class="py-2 pr-4">Default</th>
                            <th class="py-2">Description</th>
                        </tr>
                    </thead>
                    <tbody class="text-slate-300">
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200">ShowArrow</td>
                            <td class="py-2 pr-4">on</td>
                            <td class="py-2">GPS arrow pointing to navigation target</td>
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200"
                                >ShowGroundPath</td
                            >
                            <td class="py-2 pr-4">off</td>
                            <td class="py-2">Ground path line using NavMesh pathfinding</td>
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200"
                                >ShowWorldMarkers</td
                            >
                            <td class="py-2 pr-4">on</td>
                            <td class="py-2">Floating quest icons above NPCs</td>
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200"
                                >TrackerEnabled</td
                            >
                            <td class="py-2 pr-4">on</td>
                            <td class="py-2">Quest tracker overlay</td>
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200"
                                >TrackerAutoTrack</td
                            >
                            <td class="py-2 pr-4">on</td>
                            <td class="py-2">Auto-track newly accepted quests</td>
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200"
                                >ReplaceQuestLog</td
                            >
                            <td class="py-2 pr-4">off</td>
                            <td class="py-2"
                                >J opens Adventure Guide instead of the game's quest log</td
                            >
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200">UiScale</td>
                            <td class="py-2 pr-4">auto</td>
                            <td class="py-2">UI size factor (-1 = auto-detect from resolution)</td>
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200"
                                >TrackerBackgroundOpacity</td
                            >
                            <td class="py-2 pr-4">0.40</td>
                            <td class="py-2">Tracker overlay transparency</td>
                        </tr>
                        <tr class="border-b border-slate-700/50">
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200"
                                >TrackerSortMode</td
                            >
                            <td class="py-2 pr-4">Proximity</td>
                            <td class="py-2"
                                >Sort tracked quests: Proximity, Level, or Alphabetical</td
                            >
                        </tr>
                        <tr>
                            <td class="py-2 pr-4 font-mono text-xs text-slate-200">MarkerScale</td>
                            <td class="py-2 pr-4">1.0</td>
                            <td class="py-2">World marker size multiplier</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </section>
</div>

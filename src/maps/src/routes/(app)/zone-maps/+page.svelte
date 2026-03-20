<script lang="ts">
    import { MAPS } from '$lib/maps';

    const sortedMaps = Object.entries(MAPS).sort(([, a], [, b]) =>
        a.zoneName.localeCompare(b.zoneName)
    );
</script>

<!-- Maps Section -->
<div class="text-center mb-12">
    <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">Interactive Zone Maps</h2>
    <div class="w-24 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
    <p class="text-slate-400 mt-4">
        Legacy zone maps. For a unified experience, try the
        <!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
        <a href="/" class="text-purple-400 hover:text-purple-300 underline">Interactive World Map</a
        >.
    </p>
</div>

<!-- Maps grid -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
    {#each sortedMaps as [mapName, mapConfig] (mapName)}
        <!-- eslint-disable svelte/no-navigation-without-resolve -->
        <a
            href={`${mapName}`}
            class="group relative bg-slate-800 rounded-xl overflow-hidden transition-all duration-300 hover:scale-105 hover:shadow-2xl hover:shadow-purple-500/25 border border-slate-700 hover:border-purple-500/50"
        >
            <!-- eslint-enable svelte/no-navigation-without-resolve -->
            <!-- Map image -->
            <div class="aspect-video relative overflow-hidden bg-slate-700">
                <img
                    src={`/maps/${mapName}.jpg`}
                    alt={mapConfig.zoneName}
                    class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                    loading="lazy"
                />
                <!-- Gradient overlay -->
                <div
                    class="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/20 to-transparent"
                ></div>

                <!-- Hover overlay -->
                <div
                    class="absolute inset-0 bg-gradient-to-t from-purple-900/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                ></div>
            </div>

            <!-- Card content -->
            <div class="absolute bottom-0 left-0 right-0 p-4">
                <h3
                    class="text-white font-semibold text-lg mb-2 group-hover:text-purple-300 transition-colors duration-300 whitespace-pre-line"
                >
                    {mapConfig.zoneName.replace(/\((?!\d+\))/, '\n(')}
                </h3>
            </div>

            <!-- Shine effect -->
            <div
                class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700"
            >
                <div
                    class="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -skew-x-12 transform -translate-x-full group-hover:translate-x-full transition-transform duration-1000"
                ></div>
            </div>
        </a>
    {/each}
</div>

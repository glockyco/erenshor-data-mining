<!-- World Map Section -->
<div class="text-center mb-12">
    <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">Interactive World Map</h2>
    <div class="w-24 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
</div>

<!-- Hero Image -->
<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
<a
    href="/map"
    class="group block relative rounded-xl overflow-hidden transition-all duration-300 hover:shadow-2xl hover:shadow-purple-500/25 border border-slate-700 hover:border-purple-500/50"
>
    <div class="relative overflow-hidden bg-slate-700">
        <img src="/world-map-preview.webp" alt="Interactive World Map" class="w-full h-auto" />
        <!-- Gradient overlay -->
        <div
            class="absolute inset-0 bg-gradient-to-t from-slate-900/60 via-transparent to-transparent"
        ></div>

        <!-- Hover overlay -->
        <div
            class="absolute inset-0 bg-gradient-to-t from-purple-900/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end justify-center pb-8"
        >
            <span class="text-white text-xl font-semibold flex items-center">
                <svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                    ></path>
                </svg>
                Open World Map
            </span>
        </div>
    </div>
</a>

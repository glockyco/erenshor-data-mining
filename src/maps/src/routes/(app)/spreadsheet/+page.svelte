<script lang="ts">
	const sheets = [
		{
			name: "Drop Chances",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=343006502#gid=343006502",
			icon: "🎲",
		},
		{
			name: "Items",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=196960220#gid=196960220",
			icon: "🛡️"
		},
		{
			name: "Characters",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1374833096#gid=1374833096",
			icon: "🧑"
		},
		{
			name: "Classes",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1250511287#gid=1250511287",
			icon: "🧙"
		},
		{
			name: "Spells",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1445748293#gid=1445748293",
			icon: "✨"
		},
		{
			name: "Skills",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=135559765#gid=135559765",
			icon: "🛠️"
		},
		{
			name: "Ascensions",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1142473547#gid=1142473547",
			icon: "🌟"
		},
		{
			name: "Dialogs",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=173767920#gid=173767920",
			icon: "💬"
		},
		{
			name: "Quests",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=941031845#gid=941031845",
			icon: "📜"
		},
		{
			name: "Books",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=741090320#gid=741090320",
			icon: "📚"
		},
		{
			name: "Factions",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=302743318#gid=302743318",
			icon: "🤝"
		},
		{
			name: "Zones",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=475761767#gid=475761767",
			icon: "🗺️"
		},
		{
			name: "Treasure Locations",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1764162021#gid=1764162021",
			icon: "💎"
		},
		{
			name: "Teleport Destinations",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=641924033#gid=641924033",
			icon: "🌀"
		},
		{
			name: "Wishing Wells",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=681428442#gid=681428442",
			icon: "⛲"
		},
		{
			name: "Fishing Spots",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1955910737#gid=1955910737",
			icon: "🎣",
		},
		{
			name: "Mining Nodes",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=957222885#gid=957222885",
			icon: "⛏️",
		},
		{
			name: "Spawn Points",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1610341059#gid=1610341059",
			icon: "📍",
		},
		{
			name: "Secret Passages",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=20639481#gid=20639481",
			icon: "🕵️"
		},
		{
			name: "Achievement Triggers",
			url: "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?gid=1197488430#gid=1197488430",
			icon: "🏆"
		}
	];
	const sheetUrl = "https://docs.google.com/spreadsheets/d/1eOYfjaudAhvE6HGBtWyRGgQDsmWDLENaoEwRvgBO_0E/edit?usp=sharing";
</script>

<div class="text-center mb-12">
	<h2 class="text-3xl md:text-4xl font-bold text-white mb-4">Spreadsheet</h2>
	<div class="w-24 h-1 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto rounded-full"></div>
</div>

<div class="max-w-4xl mx-auto">
	<div class="bg-slate-800 rounded-xl p-8 border border-slate-700 mb-8 shadow-lg">
		<div class="text-center mb-6">
			<h3 class="text-2xl font-bold text-white mb-4">Erenshor's Secrets at Your Fingertips</h3>
			<p class="text-slate-300 text-lg leading-relaxed">
				Welcome, adventurer! Whether you’re a fresh-faced explorer or a veteran treasure hunter, this spreadsheet is your passport to all things Erenshor.<br><br>
			</p>
			<div class="mb-8 rounded-lg overflow-hidden border border-slate-600">
				<div class="bg-slate-700 flex items-center justify-center">
					<img src="/spreadsheet.png" alt="Companion Mod Demo" class="w-full object-cover"/>
				</div>
			</div>
			<p class="text-slate-300 text-lg leading-relaxed">
				Here you’ll find drop rates, items, characters, spells, skills, and much more — all extracted straight from the game files.
				Ready to dig in? Open the full sheet below, or jump straight to a specific tab using the links further down on the page.
			</p>
		</div>
		<div class="flex flex-col items-center gap-6">
			<a
				href={sheetUrl}
				target="_blank"
				rel="noopener noreferrer"
				class="inline-flex items-center px-8 py-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl text-lg"
			>
				<svg class="w-6 h-6 mr-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16h8M8 12h8m-8-4h8M4 6v12a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2z"></path>
				</svg>
				View Full Google Sheet
			</a>
			<p class="text-slate-400 text-sm mt-2">
				(Pro tip: In Google Sheets, use <b>File → Make a copy</b> to save your own, editable version.)
			</p>
		</div>
	</div>

	<div class="bg-slate-800 rounded-xl p-6 border border-slate-700">
		<h4 class="text-xl font-semibold text-white mb-4 text-center">Direct Links</h4>
		<p class="text-slate-400 text-center mb-4">
			Each tab is a trove of info — click any link to jump straight to what you need!
		</p>
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
			{#each sheets as sheet (sheet.name)}
				<a
					href={sheet.url}
					target="_blank"
					rel="noopener noreferrer"
					class="flex items-center bg-slate-700 rounded-lg px-4 py-3 border-l-4 border-purple-500 hover:border-pink-500 transition-all duration-200 shadow-sm hover:scale-105 group"
				>
					<span class="text-2xl mr-3">{sheet.icon}</span>
					<span class="font-semibold text-purple-200 group-hover:text-pink-200">{sheet.name}</span>
				</a>
			{/each}
		</div>
	</div>
</div>

return {
	["item:abyssal_plate"] = {
		stableKey = "item:abyssal_plate",
		provenanceShard = "2d",
		itemDbIndex = 102,
		kind = "armor",
		name = "Abyssal Plate",
		type = "Armor",
		icon = "Abyssal Plate icon.png",
		slot = "Chest",
		classes = { "Paladin" },
		stats = {
			{ quality = "Standard", ac = 10, hp = 225, mana = 200, str = 25, mr = 10, res = 1 },
		},
		renders = {
			{ title = "Item Picture Fixture render (male).png", body = "male" },
			{ title = "Item Picture Fixture render (female).png", body = "female" },
		},
		screenshot = "Item Picture Fixture screenshot.png",
		effects = { { kind = "wornEffect", spellKey = "spell:ancient_presence" } },
		lifecycle = { disposition = "unobtainable", notice = { update = "Fixture update" } },
		build = { gameBuildId = "fixture", publishedAt = "2026-01-01T00:00:00Z" },
	},
}

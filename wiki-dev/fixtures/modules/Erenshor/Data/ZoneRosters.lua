-- Synthetic local renderer fixture. Actual game canaries use generated data modules.
return {
	["zone:PortAzure"] = {
		{
			character = "character:a_grizzly_bear",
			tier = "enemy",
			levelMin = 9,
			levelMax = 11,
			scales = false,
			night = true,
			rare = true,
			chanceMin = 5,
			chanceMax = 10,
		},
		{
			character = "character:captain_rowan",
			tier = "npc",
			levelMin = 35,
			levelMax = 35,
			scales = false,
			night = false,
			rare = false,
			script = "FixtureEvent",
			furniture = "item:lucky_charm",
			quest = {
				key = "quest:magical_sword",
				name = "A Magical Sword in Port Azure",
				page = "A Magical Sword in Port Azure",
			},
			stopQuests = {
				{ key = "quest:catfordeer", name = "A Cat for a Deer", page = "A Cat for a Deer" },
				{ key = "quest:soulgemleah", name = "Capture Leah's Soul" },
			},
		},
	},
}

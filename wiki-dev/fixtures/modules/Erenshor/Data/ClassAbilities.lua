-- Synthetic local renderer fixture. Actual game canaries use generated data modules.
return {
	["class:druid"] = {
		{ ability = "spell:ember", level = 4, items = { "item:scroll_of_ember" } },
		{ ability = "skill:sword_mastery", level = 8, items = { "item:sword_mastery_manual" } },
	},
	["class:paladin"] = {
		{ ability = "spell:ember", level = -1, items = { "item:scroll_of_ember" } },
	},
}

return {
	["item:scroll_of_ember"] = {
		name = "Scroll of Ember",
		page = "Scroll of Ember",
		image = "Scroll of Ember.png",
		type = "Spell Scroll",
		buyValue = 300,
		sellValue = 75,
		teachesSpell = "spell:ember",
		-- Deliberately disjoint from spell:ember's UsedBy list ({Arcanist,
		-- Stormcaller}): reading a scroll is gated on the scroll's own class
		-- restrictions, so the tooltip must follow these names, not the spell's.
		classes = { "Arcanist", "Duelist" },
		classLinks = {
			{ kind = "class", stablekey = "class:arcanist" },
			{ kind = "class", stablekey = "class:duelist" },
		},
	},
}

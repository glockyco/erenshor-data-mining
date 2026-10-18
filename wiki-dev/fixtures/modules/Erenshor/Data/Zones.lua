-- Synthetic boundary cases use existing semantic-link fixture identities.
return {
	["zone:PortAzure"] = {
		{
			type = "summary",
			zoneType = "Outdoor",
			hostileCount = 3,
			scalingCount = 1,
			levelMin = 1,
			levelMedianMin = 5.5,
			levelMedianMax = 6.5,
			levelMax = 11,
		},
		{
			type = "connection",
			line = "zoneline:fixture:open",
			kind = "fixed",
			conditional = false,
			destination = {
				key = "zone:ElderstoneMines",
				name = "The Elderstone Mines",
				page = "The Elderstone Mines",
			},
		},
		{
			type = "connection",
			line = "zoneline:fixture:locked",
			kind = "fixed",
			conditional = true,
			destination = {
				key = "zone:saltedstrand",
				name = "Blacksalt Strand",
				page = "Blacksalt Strand",
			},
		},
		{
			type = "connection",
			line = "zoneline:fixture:return",
			kind = "stored_return",
			conditional = true,
		},
		{
			type = "connection",
			line = "zoneline:fixture:pageless",
			kind = "fixed",
			conditional = true,
			destination = { key = "zone:pageless-fixture", name = "Native destination" },
		},
	},
	["zone:ElderstoneMines"] = {
		{ type = "summary", zoneType = "Dungeon", hostileCount = 0, scalingCount = 0 },
	},
	["zone:saltedstrand"] = {
		{
			type = "summary",
			zoneType = "Outdoor",
			hostileCount = 1,
			scalingCount = 0,
			levelMin = 35,
			levelMedianMin = 35,
			levelMedianMax = 35,
			levelMax = 35,
		},
	},
}

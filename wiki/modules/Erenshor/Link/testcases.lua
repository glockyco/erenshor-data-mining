local Link = require("Module:Erenshor/Link")

local p = {}

local function assertContains(actual, expected, label)
	if string.find(actual, expected, 1, true) == nil then
		error(string.format("%s: expected output to contain %s", label, expected), 2)
	end
end

local function assertNotContains(actual, unexpected, label)
	if string.find(actual, unexpected, 1, true) ~= nil then
		error(string.format("%s: expected output not to contain %s", label, unexpected), 2)
	end
end

function p.run()
	local item = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		stableKey = "item:abyssal_plate",
	})
	assertContains(item, "erenshor-link erenshor-link--item", "item link has semantic class")
	assertContains(item, 'data-erenshor-page="Abyssal Plate"', "item link has target page data")
	assertContains(item, 'data-erenshor-key="item:abyssal_plate"', "item link has stable key data")
	assertContains(
		item,
		"[[File:Abyssal Plate.png|24x24px|alt=Abyssal Plate|link=Abyssal Plate]]",
		"item link has icon"
	)
	assertContains(item, "[[Abyssal Plate]]", "item link has page link")
	assertNotContains(item, 'data-erenshor-quality="', "item link omits quality by default")
	assertNotContains(
		item,
		'data-erenshor-quality="Standard"',
		"item link does not invent Standard metadata by default"
	)

	local standardItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		quality = "Standard",
	})
	assertContains(
		standardItem,
		'data-erenshor-quality="Standard"',
		"item link emits explicit Standard quality metadata"
	)
	assertNotContains(
		standardItem,
		'data-erenshor-quality="Normal"',
		"item link does not emit legacy Normal quality metadata"
	)

	local blessedItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		quality = "blessed",
	})
	assertContains(
		blessedItem,
		'data-erenshor-quality="Blessed"',
		"item link emits canonical Blessed quality"
	)

	local normalizedQualityItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		quality = "  iMpRoVeD +3  ",
	})
	assertContains(
		normalizedQualityItem,
		'data-erenshor-quality="Improved +3"',
		"item link normalizes quality case and whitespace"
	)

	for _, invalidQuality in ipairs({ "Normal", "normal", "0" }) do
		local rejected, rejectionError = pcall(function()
			Link.render({ kind = "item", page = "Abyssal Plate", quality = invalidQuality })
		end)
		if rejected then
			error("legacy item quality alias must fail fast: " .. invalidQuality, 2)
		end
		assertContains(
			rejectionError,
			"quality",
			"legacy item quality alias identifies parameter: " .. invalidQuality
		)
	end

	local invalidQualityOk, invalidQualityError = pcall(function()
		Link.render({ kind = "item", page = "Abyssal Plate", quality = "Mythic" })
	end)
	if invalidQualityOk then
		error("invalid item quality must fail fast", 2)
	end
	assertContains(invalidQualityError, "quality", "invalid item quality identifies parameter")
	assertContains(invalidQualityError, "invalid", "invalid item quality identifies invalid value")

	local stableKeyQualityItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Duplicate-page item",
		stableKey = "item:abyssal_plate",
		quality = " Blessed ",
	})
	assertContains(
		stableKeyQualityItem,
		'data-erenshor-key="item:abyssal_plate"',
		"item link preserves stable key with quality"
	)
	assertContains(
		stableKeyQualityItem,
		'data-erenshor-quality="Blessed"',
		"item link emits quality with stable key"
	)

	local itemImageOnly = Link.render({ kind = "item", page = "Abyssal Plate", imageonly = "1" })
	assertContains(
		itemImageOnly,
		"[[File:Abyssal Plate.png|24x24px|alt=Abyssal Plate|link=Abyssal Plate]]",
		"item image-only has icon"
	)
	assertNotContains(itemImageOnly, "[[Abyssal Plate]]", "item image-only suppresses text")

	local ability = Link.render({ kind = "ability", stableKey = "spell:minor_lightning" })
	assertContains(
		ability,
		"erenshor-link erenshor-link--ability",
		"ability link has semantic class"
	)
	assertContains(
		ability,
		'data-erenshor-page="Minor Lightning"',
		"ability link has target page data"
	)
	assertContains(
		ability,
		'data-erenshor-key="spell:minor_lightning"',
		"ability link has stable key data"
	)
	assertContains(
		ability,
		"[[File:Minor Lightning.png|30px|link=Minor Lightning]]",
		"ability link has icon"
	)
	assertContains(ability, "[[Minor Lightning]]", "ability link has page link")

	local quest = Link.render({ kind = "quest", page = "Reward Quest" })
	assertContains(quest, "erenshor-link erenshor-link--quest", "quest link has semantic class")
	assertContains(quest, "[[File:questiconsmall.png|link=Reward Quest]]", "quest link has icon")
	assertContains(quest, "[[Reward Quest]]", "quest link has page link")

	local character = Link.render({ kind = "character", page = "A Grizzly Bear" })
	assertContains(
		character,
		"erenshor-link erenshor-link--character",
		"character link has semantic class"
	)
	assertContains(character, "[[A Grizzly Bear]]", "character link has page link")
	assertContains(
		character,
		'data-erenshor-page="A Grizzly Bear"',
		"character link has target page data"
	)

	local punctuation = Link.render({ kind = "zone", page = "R&D <Elite>" })
	assertContains(
		punctuation,
		'data-erenshor-page="R&amp;D &lt;Elite&gt;"',
		"target page data escapes HTML-sensitive title"
	)

	local excluded = Link.render({ kind = "item", page = "-", text = "-" })
	assertNotContains(excluded, "erenshor-link", "plain excluded text has no semantic wrapper")

	local zone = Link.render({ kind = "zone", page = "Blacksalt Strand" })
	assertContains(zone, "erenshor-link erenshor-link--zone", "zone link has semantic class")
	assertContains(zone, "[[Blacksalt Strand]]", "zone link has page link")

	local faction = Link.render({ kind = "faction", page = "The Followers of Good" })
	assertContains(
		faction,
		"erenshor-link erenshor-link--faction",
		"faction link has semantic class"
	)
	assertContains(faction, "[[The Followers of Good]]", "faction link has page link")

	local class = Link.render({ kind = "class", page = "Duelist" })
	assertContains(class, "erenshor-link erenshor-link--class", "class link has semantic class")
	assertContains(class, "[[Duelist]]", "class link has page link")

	return "PASS Erenshor Link testcases"
end

return p

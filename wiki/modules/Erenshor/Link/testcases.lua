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
	assertContains(item, 'data-erenshor-kind="item"', "item link has kind data")
	assertContains(item, 'data-erenshor-key="item:abyssal_plate"', "item link has stable key data")
	assertContains(
		item,
		"[[File:Abyssal Plate.png|24x24px|alt=Abyssal Plate|link=Abyssal Plate]]",
		"item link has icon"
	)
	assertContains(item, "[[Abyssal Plate]]", "item link has page link")

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
	assertContains(ability, 'data-erenshor-kind="ability"', "ability link has kind data")
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

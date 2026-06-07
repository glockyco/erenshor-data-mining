local Character = require("Module:Erenshor/Character")

local p = {}

local function assertEqual(actual, expected, label)
	if actual ~= expected then
		error(
			string.format("%s: expected %s, got %s", label, tostring(expected), tostring(actual)),
			2
		)
	end
end

local function assertContains(actual, expected, label)
	if string.find(actual, expected, 1, true) == nil then
		error(string.format("%s: expected output to contain %s", label, expected), 2)
	end
end

function p.run()
	local bear = Character.resolve({ stablekey = "character:a_grizzly_bear" }, "Anything")
	assertEqual(bear.name, "A Grizzly Bear", "stable key resolves character")
	assertEqual(bear.type, "Enemy", "enemy type resolves")
	assertEqual(bear.health, 2340, "health resolves")

	local pageBear = Character.resolve({}, "A Grizzly Bear")
	assertEqual(pageBear.missing, true, "page title does not resolve character without stable key")

	local override = Character.resolve({
		stablekey = "character:a_grizzly_bear",
		image = "Manual Bear.png",
		faction = "-",
		class = "Ranger",
	}, "A Grizzly Bear")
	assertEqual(override.image, "Manual Bear.png", "article image override wins")
	assertEqual(override.faction, nil, "dash sentinel blanks supported fields")
	assertEqual(override.class, nil, "article class override is not supported")

	local bearKey = { stablekey = "character:a_grizzly_bear" }
	assertEqual(
		Character.fieldValue(bearKey, "A Grizzly Bear", "name"),
		"A Grizzly Bear",
		"field name resolves"
	)
	assertEqual(
		Character.fieldValue(bearKey, "A Grizzly Bear", "type"),
		"[[Enemies|Enemy]]",
		"field type formats enemy"
	)
	assertEqual(
		Character.fieldValue(bearKey, "A Grizzly Bear", "respawn"),
		"2 minutes",
		"field respawn resolves"
	)
	assertEqual(
		Character.fieldValue(bearKey, "A Grizzly Bear", "health"),
		"2340",
		"field health resolves"
	)
	assertEqual(
		Character.fieldValue(bearKey, "A Grizzly Bear", "experience"),
		"48–108",
		"field experience resolves base XP range"
	)
	assertEqual(
		Character.fieldValue(
			{ stablekey = "character:a_grizzly_bear", xpmultiplier = 6 },
			"A Grizzly Bear",
			"experience"
		),
		"288–648",
		"field experience folds boss XP multiplier into base range"
	)
	local faction = Character.fieldValue(bearKey, "A Grizzly Bear", "faction")
	assertContains(faction, "erenshor-link--faction", "faction renders semantic link")
	assertContains(faction, "[[The Followers of Evil]]", "faction includes page link")
	local zones = Character.fieldValue(bearKey, "A Grizzly Bear", "zones")
	assertContains(zones, "erenshor-link--zone", "zones render semantic links")
	assertContains(zones, "[[Blacksalt Strand]]", "zones include page link")
	local dropRates = Character.fieldValue(bearKey, "A Grizzly Bear", "droprates")
	assertContains(dropRates, "erenshor-link--item", "drop rates render semantic item links")
	assertContains(dropRates, "[[Bear Meat]]", "drop rates include item page link")
	local guaranteed = Character.fieldValue(bearKey, "A Grizzly Bear", "guaranteeddrops")
	assertContains(guaranteed, "[[Bear Pelt]]", "guaranteed pool lists guaranteed items")
	local dropRows = Character.cargoDropRows({ args = { stablekey = "character:a_grizzly_bear" } })
	assertEqual(#dropRows, 3, "cargo drop rows cover every dropped item stable key")
	assertEqual(
		dropRows[1].CharacterKey,
		"character:a_grizzly_bear",
		"drop row carries the owning character key"
	)
	assertEqual(
		dropRows[1].ItemKey,
		"item:bear_pelt",
		"drop row connects to the item by stable key"
	)
	assertEqual(dropRows[1].IsGuaranteed, "yes", "guaranteed-pool drop is flagged")
	assertEqual(dropRows[3].ItemKey, "item:bear_meat", "non-guaranteed drop is stored")
	assertEqual(dropRows[3].IsGuaranteed, "no", "non-guaranteed drop is unflagged")
	assertEqual(dropRows[3].DropProbability, "28.3", "drop row carries the probability")
	assertContains(
		Character.statusText(bearKey, "A Grizzly Bear"),
		"[[Category:Enemies]]",
		"enemy category emits"
	)

	local rowanKey = { stablekey = "character:captain_rowan" }
	assertEqual(
		Character.fieldValue(rowanKey, "Captain Rowan", "type"),
		"[[:Category:Characters|NPC]]",
		"npc type formats"
	)
	assertContains(
		Character.statusText(rowanKey, "Captain Rowan"),
		"[[Category:Characters]]",
		"npc category emits"
	)

	assertEqual(
		Character.fieldValue({}, "Unknown Prototype", "name"),
		"",
		"missing character fields are blank"
	)
	local missing = Character.statusText({}, "Unknown Prototype")
	assertContains(
		missing,
		"Missing character data: Unknown Prototype",
		"missing character is visible"
	)
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor character data]]",
		"missing character is tracked"
	)

	return "PASS Erenshor Character testcases"
end

return p

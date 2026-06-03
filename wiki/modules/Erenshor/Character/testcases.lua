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
	assertEqual(override.class, "Ranger", "article class override wins")

	local infobox =
		Character.renderInfobox({ stablekey = "character:a_grizzly_bear" }, "A Grizzly Bear")
	assertContains(infobox, "A Grizzly Bear", "infobox contains name")
	assertContains(infobox, "[[Enemies|Enemy]]", "infobox formats enemy type")
	assertContains(infobox, "2 minutes", "infobox contains respawn")
	assertContains(infobox, "[[Category:Enemies]]", "enemy category emits")

	local npc = Character.renderInfobox({ stablekey = "character:captain_rowan" }, "Captain Rowan")
	assertContains(npc, "[[:Category:Characters|NPC]]", "npc type formats")
	assertContains(npc, "[[Category:Characters]]", "npc category emits")

	local missing = Character.renderInfobox({}, "Unknown Prototype")
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

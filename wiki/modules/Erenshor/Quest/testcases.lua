local Quest = require("Module:Erenshor/Quest")

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
	local quest = Quest.resolve({ stablekey = "quest:magical_sword" }, "Anything")
	assertEqual(quest.name, "A Magical Sword in Port Azure", "stable key resolves quest")
	assertEqual(quest.experience, 450, "experience resolves")
	assertEqual(
		quest.factionChanges,
		"[[Port Azure]] +5<br>[[Sivakayans]] -2",
		"faction changes resolve"
	)

	local pageQuest = Quest.resolve({}, "A Magical Sword in Port Azure")
	assertEqual(pageQuest.missing, true, "page title does not resolve quest without stable key")

	local override = Quest.resolve({
		stablekey = "quest:magical_sword",
		title = "Manual Quest",
		location = "Manual Location",
		factionchanges = "-",
	}, "Manual Quest Override")
	assertEqual(override.name, "Manual Quest", "article title override wins")
	assertEqual(override.location, "Manual Location", "article location override wins")
	assertEqual(override.factionChanges, nil, "dash sentinel blanks supported fields")

	local questKey = { stablekey = "quest:magical_sword" }
	assertEqual(
		Quest.fieldValue(questKey, "A Magical Sword in Port Azure", "name"),
		"A Magical Sword in Port Azure",
		"field name resolves"
	)
	assertEqual(
		Quest.fieldValue(questKey, "A Magical Sword in Port Azure", "experience"),
		"450",
		"field experience resolves"
	)
	assertEqual(
		Quest.fieldValue(questKey, "A Magical Sword in Port Azure", "factionchanges"),
		"[[Port Azure]] +5<br>[[Sivakayans]] -2",
		"field faction changes resolve"
	)

	assertEqual(
		Quest.fieldValue({}, "Unknown Prototype", "name"),
		"",
		"missing quest fields are blank"
	)
	local missing = Quest.statusText({}, "Unknown Prototype")
	assertContains(missing, "Missing quest data: Unknown Prototype", "missing quest is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor quest data]]",
		"missing quest is tracked"
	)

	return "PASS Erenshor Quest testcases"
end

return p

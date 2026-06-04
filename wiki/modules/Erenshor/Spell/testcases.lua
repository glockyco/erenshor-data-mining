local Spell = require("Module:Erenshor/Spell")

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
	local spell = Spell.resolve({ stablekey = "spell:minor_lightning" }, "Anything")
	assertEqual(spell.name, "Minor Lightning", "stable key resolves spell")
	assertEqual(spell.targetDamage, 85, "numeric spell field resolves")

	local pageSpell = Spell.resolve({}, "Minor Lightning")
	assertEqual(pageSpell.missing, true, "page title does not resolve spell without stable key")

	local override = Spell.resolve(
		{ stablekey = "spell:minor_lightning", title = "Manual Spell", damage_type = "-" },
		"Manual Spell Override"
	)
	assertEqual(override.name, "Manual Spell", "article title override wins")
	assertEqual(override.damageType, nil, "dash sentinel blanks supported fields")

	local minor = { stablekey = "spell:minor_lightning" }
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "title"),
		"Minor Lightning",
		"field title resolves"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "image"),
		"Minor Lightning.png",
		"image formats"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "imagecaption"),
		"You are overcome by electricity.",
		"image caption formats from player message"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "classes"),
		"[[Druid]] (6)<br>[[Stormcaller]] (6)",
		"classes include required level"
	)
	assertEqual(Spell.fieldValue(minor, "Minor Lightning", "manacost"), "30", "mana formats")
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "casttime"),
		"2.3 seconds",
		"cast time formats"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "cooldown"),
		"8 seconds",
		"cooldown formats"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "duration"),
		"",
		"zero duration is hidden"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "damage_type"),
		"Magic",
		"damage type formats"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "target_damage"),
		"85",
		"target damage formats"
	)
	assertEqual(Spell.fieldValue(minor, "Minor Lightning", "aggro"), "60", "aggro formats")
	assertEqual(Spell.statusText(minor, "Minor Lightning"), "", "present spell status is blank")

	local buff = { stablekey = "spell:ancient_presence" }
	assertEqual(
		Spell.fieldValue(buff, "Ancient Presence", "duration"),
		"12 seconds",
		"duration ticks convert"
	)
	assertEqual(
		Spell.fieldValue(buff, "Ancient Presence", "duration_in_ticks"),
		"4 ticks",
		"duration ticks expose raw value"
	)
	assertEqual(
		Spell.fieldValue(buff, "Ancient Presence", "damage_shield"),
		"40",
		"stat effect formats"
	)

	assertEqual(
		Spell.fieldValue({}, "Unknown Spell", "title"),
		"",
		"missing spell fields are blank"
	)
	local missing = Spell.statusText({}, "Unknown Spell")
	assertContains(missing, "Missing spell data: Unknown Spell", "missing spell is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor spell data]]",
		"missing spell is tracked"
	)

	return "PASS Erenshor Spell testcases"
end

return p

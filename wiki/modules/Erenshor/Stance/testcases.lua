local Stance = require("Module:Erenshor/Stance")

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
	local stance = Stance.resolve({ stablekey = "stance:aggressive" }, "Anything")
	assertEqual(stance.name, "Aggressive", "stable key resolves stance")
	assertEqual(stance.stopRegen, true, "boolean stance field resolves")

	local pageStance = Stance.resolve({}, "Aggressive")
	assertEqual(pageStance.missing, true, "page title does not resolve stance without stable key")

	local override = Stance.resolve(
		{ stablekey = "stance:aggressive", title = "Manual Stance", damage_mod = "-" },
		"Manual Stance Override"
	)
	assertEqual(override.name, "Manual Stance", "article title override wins")
	assertEqual(override.damageMod, nil, "dash sentinel blanks supported fields")

	local aggressiveKey = { stablekey = "stance:aggressive" }
	assertEqual(
		Stance.fieldValue(aggressiveKey, "Aggressive", "title"),
		"Aggressive",
		"field title resolves"
	)
	assertEqual(
		Stance.fieldValue(aggressiveKey, "Aggressive", "damage_mod"),
		"+40%",
		"damage modifier formats"
	)
	assertEqual(
		Stance.fieldValue(aggressiveKey, "Aggressive", "spell_damage_mod"),
		"—",
		"neutral spell damage formats"
	)
	assertEqual(
		Stance.fieldValue(aggressiveKey, "Aggressive", "stop_regen"),
		"Yes",
		"stop regen formats"
	)
	assertContains(
		Stance.fieldValue(aggressiveKey, "Aggressive", "activated_by"),
		"Stance: Aggressive",
		"activated-by derives from skills"
	)
	assertEqual(
		Stance.statusText(aggressiveKey, "Aggressive"),
		"",
		"present stance status is blank"
	)

	local recklessKey = { stablekey = "stance:reckless" }
	assertEqual(
		Stance.fieldValue(recklessKey, "Reckless", "self_damage_per_attack"),
		"4% max HP",
		"self-damage per attack formats"
	)
	assertEqual(
		Stance.fieldValue(recklessKey, "Reckless", "stop_regen"),
		"",
		"false stop regen is hidden"
	)

	assertEqual(
		Stance.fieldValue({}, "Unknown Prototype", "title"),
		"",
		"missing stance fields are blank"
	)
	local missing = Stance.statusText({}, "Unknown Prototype")
	assertContains(missing, "Missing stance data: Unknown Prototype", "missing stance is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor stance data]]",
		"missing stance is tracked"
	)

	local cargo = Stance.cargoArgs({ args = { stablekey = "stance:aggressive" } })
	assertEqual(cargo.Name, "Aggressive", "stance cargo row name")
	assertEqual(
		cargo.Image,
		"Stance: Aggressive.png",
		"stance cargo image derives from the activating skill"
	)
	assertEqual(cargo.DamageMod, "1.4", "stance cargo stores the raw damage multiplier")
	assertEqual(cargo.DamageTakenMod, "1.4", "stance cargo stores the raw damage-taken multiplier")
	assertEqual(cargo.MaxHpMod, "1", "stance cargo stores a neutral multiplier as 1")
	assertEqual(cargo.SelfDamagePerAttack, "0", "stance cargo stores zero self-damage")
	assertEqual(cargo.StopRegen, "yes", "stance cargo true boolean casts to yes")

	local reckless = Stance.cargoArgs({ args = { stablekey = "stance:reckless" } })
	assertEqual(reckless.DamageMod, "2", "reckless stance damage multiplier")
	assertEqual(reckless.SelfDamagePerAttack, "4", "reckless self-damage per attack")
	assertEqual(reckless.StopRegen, "no", "reckless false boolean casts to no")

	return "PASS Erenshor Stance testcases"
end

return p

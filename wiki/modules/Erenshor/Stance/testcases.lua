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
	local aggressiveTip = Stance.renderTooltip(aggressiveKey, "Aggressive")
	assertContains(
		aggressiveTip,
		'class="erenshor-ability-tooltip item-spell-details item-spell-details-standalone"',
		"stance tooltip root has exact classes"
	)
	assertContains(aggressiveTip, 'data-erenshor-kind="stance"', "stance tooltip root has kind")
	assertContains(
		aggressiveTip,
		'data-erenshor-key="stance:aggressive"',
		"stance tooltip root has stable key"
	)
	assertContains(
		aggressiveTip,
		"Change Stance",
		"stance tooltip uses activating skill presentation"
	)

	local recklessTip = Stance.renderTooltip(recklessKey, "Reckless")
	assertContains(
		recklessTip,
		'data-erenshor-key="stance:reckless"',
		"fallback stance tooltip keeps stance identity"
	)
	assertContains(
		recklessTip,
		"Reckless - Activatable",
		"fallback stance tooltip synthesizes skill"
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
	assertContains(
		Stance.renderTooltip({}, "Unknown Prototype"),
		"Missing stance data: Unknown Prototype",
		"missing direct stance tooltip is visible"
	)
	assertEqual(
		Stance.renderPageTooltip({}, "Unknown Prototype"),
		"",
		"missing page stance tooltip is silent"
	)

	return "PASS Erenshor Stance testcases"
end

return p

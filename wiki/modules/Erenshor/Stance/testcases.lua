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

	local original = Stance.resolve(
		{ stablekey = "stance:aggressive", title = "Manual Stance", damage_mod = "-" },
		"Manual Stance Override"
	)
	assertEqual(original.name, "Aggressive", "article parameters do not change stance data")
	assertEqual(original.damageMod, 1.4, "article parameters do not blank stance data")

	local aggressiveKey = { stablekey = "stance:aggressive" }
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

	local recklessKey = { stablekey = "stance:reckless" }
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

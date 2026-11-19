local Skill = require("Module:Erenshor/Skill")

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
	local skill = Skill.resolve({ stablekey = "skill:backstab" }, "Anything")
	assertEqual(skill.name, "Backstab", "stable key resolves skill")
	assertEqual(skill.requireBehind, true, "boolean skill field resolves")

	local pageSkill = Skill.resolve({}, "Backstab")
	assertEqual(pageSkill.missing, true, "page title does not resolve skill without stable key")

	local original = Skill.resolve(
		{ stablekey = "skill:backstab", title = "Manual Skill", damage_type = "-" },
		"Manual Skill Override"
	)
	assertEqual(original.name, "Backstab", "article parameters do not change skill data")
	assertEqual(original.damageType, "Physical", "article parameters do not blank skill data")

	local backstabTip = Skill.renderTooltip({ stablekey = "skill:backstab" }, "Backstab")
	assertContains(
		backstabTip,
		'item-spell-details-header">Backstab</div><div class="item-ability-kind">Ability',
		"attack skill card shows its name and kind"
	)
	assertContains(
		backstabTip,
		"Deal major damage to your target",
		"attack skill tooltip shows description"
	)
	assertContains(
		backstabTip,
		'class="erenshor-ability-tooltip item-spell-details item-spell-details-standalone"',
		"skill tooltip root has exact classes"
	)
	assertContains(backstabTip, 'data-erenshor-kind="skill"', "skill tooltip default kind")
	assertContains(
		backstabTip,
		'data-erenshor-key="skill:backstab"',
		"skill tooltip default stable key"
	)

	local passiveTip = Skill.renderTooltip({ stablekey = "skill:sword_mastery" }, "Sword Mastery")
	assertContains(
		passiveTip,
		'item-spell-details-header">Sword Mastery</div><div class="item-ability-kind">Ability',
		"innate skill card uses the same ability subtitle"
	)

	local stanceTip =
		Skill.renderTooltip({ stablekey = "skill:stance - aggressive" }, "Stance: Aggressive")
	assertContains(
		stanceTip,
		'item-spell-details-header">Stance: Aggressive',
		"stance skill tooltip title"
	)
	if string.find(stanceTip, "Change Stance", 1, true) then
		error("stance skill tooltip uses hotkey text, not skillbook activation text")
	end
	assertContains(
		stanceTip,
		"Gain a 50% increase to physical damage",
		"stance skill tooltip shows the hotkey description"
	)

	local missingTip = Skill.renderTooltip({}, "Unknown Skill")
	assertContains(
		missingTip,
		"Missing skill data: Unknown Skill",
		"missing skill tooltip is visible"
	)
	assertEqual(
		Skill.renderPageTooltip({}, "Unknown Skill"),
		"",
		"missing page skill tooltip is silent"
	)

	return "PASS Erenshor Skill testcases"
end

return p

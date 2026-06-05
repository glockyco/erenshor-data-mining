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

	local override = Skill.resolve(
		{ stablekey = "skill:backstab", title = "Manual Skill", damage_type = "-" },
		"Manual Skill Override"
	)
	assertEqual(override.name, "Manual Skill", "article title override wins")
	assertEqual(override.damageType, nil, "dash sentinel blanks supported fields")

	local backstab = { stablekey = "skill:backstab" }
	assertEqual(Skill.fieldValue(backstab, "Backstab", "title"), "Backstab", "field title resolves")
	assertEqual(Skill.fieldValue(backstab, "Backstab", "image"), "Backstab.png", "image formats")
	assertEqual(Skill.fieldValue(backstab, "Backstab", "type"), "Attack", "type formats")
	assertEqual(
		Skill.fieldValue({ stablekey = "skill:sword_mastery" }, "Sword Mastery", "type"),
		"Passive",
		"innate skill type displays as passive"
	)
	local classes = Skill.fieldValue(backstab, "Backstab", "classes")
	assertContains(classes, "erenshor-link--class", "class levels render semantic class links")
	assertContains(classes, "Windblade", "class levels include display name")
	assertContains(classes, "(2)", "class levels include level")
	assertEqual(
		Skill.fieldValue(backstab, "Backstab", "casttime"),
		"Instant",
		"skill cast time formats"
	)
	assertEqual(
		Skill.fieldValue(backstab, "Backstab", "cooldown"),
		"9 seconds",
		"skill cooldown ticks convert"
	)
	assertEqual(
		Skill.fieldValue(backstab, "Backstab", "damage_type"),
		"Physical",
		"damage type formats"
	)
	assertEqual(
		Skill.fieldValue(backstab, "Backstab", "target_damage"),
		"7",
		"target damage reads generated skill power"
	)
	local source = Skill.fieldValue(backstab, "Backstab", "source")
	assertContains(source, "erenshor-link--item", "source renders semantic item link")
	assertContains(source, "[[Sword Mastery Manual]]", "source includes teaching item")
	local itemsWithEffect = Skill.fieldValue(backstab, "Backstab", "itemswitheffect")
	assertContains(
		itemsWithEffect,
		"erenshor-link--item",
		"items with effect render semantic item link"
	)
	assertContains(
		itemsWithEffect,
		"[[Sword Mastery Manual]]",
		"items with effect include source item"
	)
	assertEqual(
		Skill.fieldValue(backstab, "Backstab", "special_descriptor"),
		"Behind target",
		"requirements format"
	)
	assertEqual(Skill.statusText(backstab, "Backstab"), "", "present skill status is blank")

	local stance = { stablekey = "skill:stance - aggressive" }
	local stanceClasses = Skill.fieldValue(stance, "Stance: Aggressive", "classes")
	assertContains(
		stanceClasses,
		"erenshor-link--class",
		"stance skill class renders semantic class link"
	)
	assertContains(stanceClasses, "Reaver", "stance skill class includes display name")
	assertContains(stanceClasses, "(1)", "stance skill class includes level")
	assertContains(
		Skill.fieldValue(stance, "Stance: Aggressive", "effects"),
		"Aggressive",
		"stance skill effects link stance"
	)
	assertEqual(
		Skill.fieldValue(stance, "Stance: Aggressive", "cooldown"),
		"",
		"zero cooldown is hidden"
	)

	assertEqual(
		Skill.fieldValue({}, "Unknown Skill", "title"),
		"",
		"missing skill fields are blank"
	)
	local missing = Skill.statusText({}, "Unknown Skill")
	assertContains(missing, "Missing skill data: Unknown Skill", "missing skill is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor skill data]]",
		"missing skill is tracked"
	)

	local backstabTip = Skill.renderTooltip({ stablekey = "skill:backstab" }, "Backstab")
	assertContains(
		backstabTip,
		"Backstab - Activatable",
		"attack skill tooltip title shows activatable"
	)
	assertContains(
		backstabTip,
		"Deal major damage to your target",
		"attack skill tooltip shows description"
	)
	assertContains(
		backstabTip,
		"item-spell-details-standalone",
		"standalone skill tooltip has a top border"
	)

	local passiveTip = Skill.renderTooltip({ stablekey = "skill:sword_mastery" }, "Sword Mastery")
	assertContains(
		passiveTip,
		"Sword Mastery - Passive",
		"innate skill tooltip title shows passive"
	)

	local stanceTip =
		Skill.renderTooltip({ stablekey = "skill:stance - aggressive" }, "Stance: Aggressive")
	assertContains(stanceTip, "Stance: Aggressive - Activatable", "stance skill tooltip title")
	assertContains(stanceTip, "Change Stance", "stance skill tooltip shows change stance")
	assertContains(stanceTip, "Aggressive", "stance skill tooltip shows stance name")
	assertContains(
		stanceTip,
		"Gain a 40% increase to physical damage",
		"stance skill tooltip shows stance description"
	)

	local missingTip = Skill.renderTooltip({}, "Unknown Skill")
	assertContains(
		missingTip,
		"Missing skill data: Unknown Skill",
		"missing skill tooltip is visible"
	)

	return "PASS Erenshor Skill testcases"
end

return p

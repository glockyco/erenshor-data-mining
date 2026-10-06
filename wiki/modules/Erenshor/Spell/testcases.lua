local Spell = require("Module:Erenshor/Spell")
local Tooltip = require("Module:Erenshor/Spell/Tooltip")
local Common = require("Module:Erenshor/Ability/Common")

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

local function assertNotContains(actual, unexpected, label)
	if string.find(actual, unexpected, 1, true) ~= nil then
		error(string.format("%s: expected output not to contain %s", label, unexpected), 2)
	end
end

function p.run()
	local ok, err = pcall(Common.standaloneTooltipRoot, "item", "spell:bad")
	assertEqual(ok, false, "unsupported standalone tooltip identity is rejected")
	assertContains(
		tostring(err),
		"Standalone ability tooltip requires spell, skill, or stance kind and a stable key",
		"invalid identity reports the contract"
	)
	local blankOk = pcall(Common.standaloneTooltipRoot, "spell", " ")
	assertEqual(blankOk, false, "blank standalone tooltip key is rejected")

	local spell = Spell.resolve({ stablekey = "spell:minor_lightning" }, "Anything")
	assertEqual(spell.name, "Minor Lightning", "stable key resolves spell")
	assertEqual(spell.targetDamage, 85, "numeric spell field resolves")

	local pageSpell = Spell.resolve({}, "Minor Lightning")
	assertEqual(pageSpell.missing, true, "page title does not resolve spell without stable key")

	local original = Spell.resolve(
		{ stablekey = "spell:minor_lightning", title = "Manual Spell", damage_type = "-" },
		"Manual Spell Override"
	)
	assertEqual(original.name, "Minor Lightning", "article parameters do not change spell data")
	assertEqual(original.damageType, "Magic", "article parameters do not blank spell data")

	local minor = { stablekey = "spell:minor_lightning" }
	local minorTooltip = Spell.renderTooltip(minor, "Minor Lightning")
	assertContains(minorTooltip, "Spell Level: 6", "spell tooltip includes item-detail level")
	assertContains(
		minorTooltip,
		'class="erenshor-icon erenshor-icon--bare"',
		"spell tooltip shows the bare icon of the item window's spell details"
	)
	assertContains(
		minorTooltip,
		"[[File:Minor Lightning.png|48x48px]]",
		"spell tooltip fits art at 48 px"
	)
	assertNotContains(minorTooltip, "Hotbar Frame.png", "spell tooltip draws no frame")
	assertContains(
		minorTooltip,
		"Spell Line: Direct_Damage",
		"spell tooltip includes item-detail line"
	)
	assertContains(minorTooltip, "Resonance ", "spell tooltip includes item-detail resonance")
	assertContains(minorTooltip, "+30", "spell tooltip includes resonance value")
	assertContains(
		minorTooltip,
		"Armor Penetration ",
		"spell tooltip includes spellbook armor penetration"
	)
	assertContains(minorTooltip, "+12%", "spell tooltip includes armor penetration value")
	assertContains(
		minorTooltip,
		"Mana Regen ",
		"spell tooltip includes level-scaled mana restoration"
	)
	assertContains(
		minorTooltip,
		'<span class="item-spell-positive">+1.5</span> per level',
		"spell tooltip labels level scaling"
	)
	assertContains(minorTooltip, "25% chance to proc", "spell tooltip includes added proc chance")
	local hydrated =
		Tooltip.render({ stableKey = "spell:all - hydrated", name = "Hydrated", haste = 3 })
	assertContains(
		hydrated,
		'Haste <span class="item-spell-positive">+3%</span>',
		"haste uses the spell-details percent unit"
	)
	assertContains(minorTooltip, "[[Ancient Presence]]", "spell tooltip links the added proc")

	local buffTip =
		Spell.renderTooltip({ stablekey = "spell:ancient_presence" }, "Ancient Presence")
	assertContains(buffTip, "Effect Duration: 12 sec", "buff tooltip shows effect duration")
	assertContains(buffTip, "Spell Type: Beneficial", "buff tooltip shows spell type")
	assertContains(buffTip, "Mana Cost: 0", "buff tooltip shows mana cost")
	assertContains(buffTip, "Cast Time: 0.0 sec", "buff tooltip shows cast time")
	assertContains(buffTip, "Cooldown: 0 sec", "buff tooltip shows cooldown")
	assertContains(buffTip, "Group Effect", "buff tooltip shows group effect flag")
	assertContains(
		buffTip,
		'Hitpoints <span class="item-spell-positive">+500</span>',
		"buff tooltip shows hp modifier"
	)
	assertContains(
		buffTip,
		'Damage Shield <span class="item-spell-positive">+40</span>',
		"buff tooltip shows damage shield modifier"
	)
	assertContains(
		buffTip,
		'Strength <span class="item-spell-positive">+20</span>',
		"buff tooltip shows strength modifier"
	)
	assertContains(
		buffTip,
		'class="erenshor-ability-tooltip item-spell-details item-spell-details-standalone"',
		"spell tooltip root has exact classes"
	)
	assertContains(buffTip, 'data-erenshor-kind="spell"', "spell tooltip root has kind")
	assertContains(
		buffTip,
		'data-erenshor-key="spell:ancient_presence"',
		"spell tooltip root has stable key"
	)
	assertContains(
		buffTip,
		"item-spell-details-spacer",
		"spell tooltip balances the icon so the title centers"
	)

	local dmgTip = Spell.renderTooltip({ stablekey = "spell:minor_lightning" }, "Minor Lightning")
	assertContains(dmgTip, "Instant Effect", "damage tooltip shows instant effect")
	assertContains(dmgTip, "Mana Cost: 30", "damage tooltip shows mana cost")
	assertContains(dmgTip, "Damage: 85", "damage tooltip shows damage")
	assertContains(dmgTip, "Cast Time: 2.3 sec", "damage tooltip shows cast time")
	assertContains(dmgTip, "Cooldown: 8 sec", "damage tooltip shows cooldown")
	assertContains(
		dmgTip,
		'Resist Type: <span style="color:#8080FF">Magic</span>',
		"damage tooltip shows colored resist type"
	)

	local missingTip = Spell.renderTooltip({}, "Unknown Spell")
	assertContains(
		missingTip,
		"Missing spell data: Unknown Spell",
		"missing spell tooltip is visible"
	)
	assertEqual(
		Spell.renderPageTooltip({}, "Unknown Spell"),
		"",
		"missing page spell tooltip is silent"
	)

	return "PASS Erenshor Spell testcases"
end

return p

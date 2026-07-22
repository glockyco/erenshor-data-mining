local Spell = require("Module:Erenshor/Spell")
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
	local classes = Spell.fieldValue(minor, "Minor Lightning", "classes")
	assertContains(classes, "erenshor-link--class", "classes render semantic class links")
	assertContains(classes, "Druid", "classes include Druid")
	assertContains(classes, "Stormcaller", "classes include Stormcaller")
	assertContains(
		classes,
		'data-erenshor-key="class:duelist"',
		"generated spell classes carry stable class identity"
	)
	assertContains(
		classes,
		'data-erenshor-page="Windblade"',
		"generated spell classes use canonical class page"
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
	local itemsWithEffect = Spell.fieldValue(minor, "Minor Lightning", "itemswitheffect")
	assertContains(
		itemsWithEffect,
		"erenshor-link--item",
		"items with effect render semantic item links"
	)
	assertContains(itemsWithEffect, "[[Abyssal Plate]]", "items with effect include Abyssal Plate")
	assertContains(
		itemsWithEffect,
		"[[Healing Draught]]",
		"items with effect include Healing Draught"
	)
	local source = Spell.fieldValue(minor, "Minor Lightning", "source")
	assertContains(source, "erenshor-link--item", "source renders semantic item link")
	assertContains(source, "[[Scroll of Ember]]", "source includes teaching item")
	local usedBy = Spell.fieldValue(minor, "Minor Lightning", "used_by")
	assertContains(usedBy, "erenshor-link--character", "used by renders semantic character link")
	assertContains(usedBy, "[[Rare Cave Spider]]", "used by includes caster page")
	local pet = Spell.fieldValue(minor, "Minor Lightning", "pet_to_summon")
	assertContains(pet, "erenshor-link--character", "pet summon renders semantic character link")
	assertContains(pet, "[[A Grizzly Bear]]", "pet summon includes character page")
	assertEqual(Spell.statusText(minor, "Minor Lightning"), "", "present spell status is blank")

	local buff = { stablekey = "spell:ancient_presence" }
	assertEqual(
		Spell.fieldValue(buff, "Ancient Presence", "duration"),
		"12 seconds",
		"duration in seconds"
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

	local cargo = Spell.cargoArgs({ args = { stablekey = "spell:minor_lightning" } })
	assertEqual(cargo.Name, "Minor Lightning", "spell cargo row name")
	assertEqual(cargo.Type, "AE", "spell cargo row type")
	assertEqual(cargo.Line, "Direct_Damage", "spell cargo row line")
	assertEqual(cargo.RequiredLevel, "6", "spell cargo row required level")
	assertEqual(cargo.ManaCost, "30", "spell cargo row mana cost")
	assertEqual(cargo.CastTimeSeconds, "2.33", "spell cargo row cast time in seconds")
	assertEqual(cargo.CooldownSeconds, "8", "spell cargo row cooldown in seconds")
	assertEqual(cargo.CastRange, "30", "spell cargo row range")
	assertEqual(cargo.DamageType, "Magic", "spell cargo row damage type")
	assertEqual(cargo.TargetDamage, "85", "spell cargo row target damage")
	assertEqual(cargo.Aggro, "60", "spell cargo row aggro")
	assertEqual(cargo.SimUsable, "yes", "spell cargo row true boolean casts to yes")
	assertEqual(cargo.SelfOnly, "no", "spell cargo row false boolean casts to no")
	assertEqual(
		cargo.PetToSummonKey,
		"character:a_grizzly_bear",
		"spell cargo row stores the pet stable key"
	)
	assertEqual(cargo.GrantInvisibility, nil, "spell cargo row omits absent boolean flags")

	local classRows = Spell.cargoClassRows({ args = { stablekey = "spell:minor_lightning" } })
	assertEqual(#classRows, 3, "spell emits one AbilityClasses row per class")
	assertEqual(
		classRows[1].AbilityKey,
		"spell:minor_lightning",
		"class row carries the stable key"
	)
	assertEqual(classRows[1].Class, "Druid", "first class row is Druid")
	assertEqual(classRows[1].RequiredLevel, "6", "class row broadcasts the spell required level")
	assertEqual(classRows[2].Class, "Duelist", "second class row is Duelist")
	assertEqual(classRows[3].Class, "Stormcaller", "third class row is Stormcaller")

	local noClassRows = Spell.cargoClassRows({ args = { stablekey = "spell:ancient_presence" } })
	assertEqual(#noClassRows, 0, "a spell with no classes emits no AbilityClasses rows")

	-- Multi-entity: two spells share a display name but are distinct stable keys, so
	-- one page can store two independent Spells rows keyed by StableKey, not Name.
	local lesser = Spell.cargoArgs({ args = { stablekey = "spell:flame_bolt" } })
	local greater = Spell.cargoArgs({ args = { stablekey = "spell:flame_bolt_greater" } })
	assertEqual(lesser.Name, "Flame Bolt", "lesser flame bolt name")
	assertEqual(greater.Name, "Flame Bolt", "greater flame bolt shares the display name")
	assertEqual(lesser.StableKey, "spell:flame_bolt", "lesser flame bolt stable key")
	assertEqual(
		greater.StableKey,
		"spell:flame_bolt_greater",
		"greater flame bolt distinct stable key"
	)
	assertEqual(lesser.TargetDamage, "50", "lesser flame bolt damage")
	assertEqual(greater.TargetDamage, "130", "greater flame bolt damage")

	return "PASS Erenshor Spell testcases"
end

return p

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
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "itemswitheffect"),
		"{{ItemLink|Abyssal Plate}}<br>{{ItemLink|Healing Draught}}",
		"items with effect join generated relationship list"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "source"),
		"{{ItemLink|Scroll of Ember}}",
		"source joins generated teaching items"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "used_by"),
		"[[Rare Cave Spider]]",
		"used by joins generated caster list"
	)
	assertEqual(
		Spell.fieldValue(minor, "Minor Lightning", "pet_to_summon"),
		"[[A Grizzly Bear]]",
		"pet stable key resolves generated character link"
	)
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
		"item-spell-details-standalone",
		"standalone spell tooltip has a top border"
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

	return "PASS Erenshor Spell testcases"
end

return p

local Item = require("Module:Erenshor/Item")

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
	local weapon = Item.resolve({ stablekey = "item:ember_longsword" }, "Anything")
	assertEqual(weapon.name, "Ember Longsword", "stable key resolves item")
	assertEqual(weapon.type, "Weapon", "weapon type resolves")
	assertEqual(weapon.damage, 18, "weapon damage resolves")

	local pageWeapon = Item.resolve({}, "Ember Longsword")
	assertEqual(pageWeapon.missing, true, "page title does not resolve item without stable key")

	local override = Item.resolve({
		stablekey = "item:ember_longsword",
		image = "Manual.png",
		othersource = "Quest reward",
		slot = "Secondary",
		itemlevel = "13",
	}, "Ember Longsword")
	assertEqual(override.image, "Manual.png", "article image override wins")
	assertEqual(override.othersource, "Quest reward", "manual source override wins")
	assertEqual(override.slot, "Secondary", "article slot override wins")
	assertEqual(override.itemLevel, "13", "article item level override wins")

	local blanked =
		Item.resolve({ stablekey = "item:ember_longsword", image = "-" }, "Ember Longsword")
	assertEqual(blanked.image, nil, "dash sentinel blanks supported fields")

	local weaponKey = { stablekey = "item:ember_longsword" }
	assertEqual(
		Item.fieldValue(weaponKey, "Ember Longsword", "name"),
		"Ember Longsword",
		"field name resolves"
	)
	assertEqual(
		Item.fieldValue(weaponKey, "Ember Longsword", "damage"),
		"18",
		"field damage resolves"
	)
	assertEqual(
		Item.fieldValue(weaponKey, "Ember Longsword", "buy"),
		"12500",
		"field buy renders the raw gold value"
	)

	local cargo = Item.cargoStore({
		args = { stablekey = "item:abyssal_plate" },
		preprocess = function(_, text)
			return text
		end,
	})
	assertContains(cargo, "|Armor=40", "cargo store contains armor overview AC")
	assertContains(
		cargo,
		"|ClassLinks=[[Paladin]], [[Warrior]]",
		"cargo store contains class links"
	)
	assertEqual(
		Item.fieldValue({ stablekey = "item:healing_draught" }, "Healing Draught", "disposable"),
		"Yes",
		"consumable disposable field renders Yes"
	)
	assertEqual(
		Item.fieldValue(
			{ stablekey = "item:healing_draught", disposable = "no" },
			"Healing Draught",
			"disposable"
		),
		"",
		"non-consumable disposable row hides like live"
	)

	local weaponTooltip =
		Item.renderTooltip({ stablekey = "item:ember_longsword" }, "Ember Longsword")
	assertContains(
		weaponTooltip,
		"item-tooltip-weapon",
		"weapon tooltip carries the weapon CSS class"
	)
	assertContains(weaponTooltip, "Ember Longsword", "weapon tooltip shows the item name")
	assertContains(weaponTooltip, "item-tooltip-tier-0", "weapon tooltip colors the Normal quality")
	assertContains(
		weaponTooltip,
		"item-tooltip-tier-2",
		"weapon tooltip colors the Ascended quality"
	)
	if string.find(weaponTooltip, "Godly", 1, true) ~= nil then
		error("weapon tooltip must not expose the internal Godly label", 2)
	end
	assertContains(weaponTooltip, "Base DPS:", "weapon tooltip shows base DPS")
	assertContains(weaponTooltip, "Paladin", "weapon tooltip shows class restrictions")
	assertContains(
		weaponTooltip,
		"item-tooltip-two-column",
		"weapon tooltip uses the two-column body"
	)
	assertContains(weaponTooltip, "Vitals", "weapon tooltip shows the Vitals section")
	assertContains(weaponTooltip, "Resists", "weapon tooltip shows the Resists section")
	assertContains(weaponTooltip, "+0%", "weapon tooltip shows resists in +N% form")
	assertContains(
		weaponTooltip,
		"Slot: [[Weapons#Primary|Primary]]",
		"weapon shows the game slot prefix"
	)
	assertContains(weaponTooltip, "Range", "weapon shows the range row (melee = 1)")

	local charm = Item.renderTooltip({ stablekey = "item:lucky_charm" }, "Lucky Charm")
	assertContains(charm, "item-tooltip-charm", "charm tooltip carries the charm CSS class")
	assertContains(charm, "Charm Item", "charm tooltip shows the charm label")
	assertContains(charm, "Arcanism: +10 / 40", "charm scaling uses the game attribute names")
	assertContains(weaponTooltip, "item-spell-details", "weapon proc shows spell details")
	assertContains(
		weaponTooltip,
		"20% chance on ATTACK:",
		"weapon proc header uses the game trigger style"
	)
	assertContains(weaponTooltip, "Ember Burst", "weapon proc shows the effect spell name")

	local consumable = Item.renderTooltip({ stablekey = "item:healing_draught" }, "Healing Draught")
	assertContains(consumable, "item-tooltip-consumable", "consumable tooltip CSS class")
	assertContains(
		consumable,
		"Item Consumed Upon Use.",
		"disposable consumable shows the consumed notice"
	)
	assertContains(consumable, "Activatable: Minor Heal", "consumable shows the activatable effect")
	assertContains(consumable, "item-spell-details", "consumable shows spell details")
	assertContains(consumable, "Healing: 150", "consumable spell details show healing")

	local mold = Item.renderTooltip({ stablekey = "item:copper_armor_mold" }, "Copper Armor Mold")
	assertContains(mold, "Ingredients:", "mold tooltip shows ingredients")
	assertContains(mold, "Creates:", "mold tooltip shows created items")

	local aura = Item.renderTooltip({ stablekey = "item:ember_aura" }, "Ember Aura")
	assertContains(aura, "Aura Item", "aura tooltip shows the aura label")
	assertContains(aura, "Auras effect entire party", "aura tooltip shows the party note")
	assertContains(aura, "item-spell-details", "aura shows spell details")
	assertContains(aura, "Group Effect", "aura spell details show the group-effect flag")

	local skillBook =
		Item.renderTooltip({ stablekey = "item:sword_mastery_manual" }, "Sword Mastery Manual")
	assertContains(skillBook, "item-tooltip-book", "skill book carries the book CSS class")
	assertContains(skillBook, "Required Level:", "skill book shows the requirement header")
	assertContains(
		skillBook,
		"Windblade: 3",
		"skill book shows per-class levels with display names"
	)
	assertContains(skillBook, "Skill Type: Passive", "skill book shows the skill type")
	assertContains(
		skillBook,
		"SimPlayers DO NOT automatically learn",
		"skill book warns when not auto-learned"
	)

	local spellScroll =
		Item.renderTooltip({ stablekey = "item:scroll_of_ember" }, "Scroll of Ember")
	assertContains(spellScroll, "item-tooltip-book", "spell scroll carries the book CSS class")
	assertContains(
		spellScroll,
		"Arcanist: 8",
		"spell scroll shows the required level per usable class"
	)
	assertContains(spellScroll, "Mana Cost: 25", "spell scroll shows the mana cost")
	assertContains(spellScroll, "Spell Type: Damage", "spell scroll shows the spell type")

	assertContains(weaponTooltip, "[[Category:Weapons]]", "weapon emits the weapon category")
	assertContains(weaponTooltip, "[[Category:Primary Weapons]]", "weapon emits the slot category")
	assertContains(
		weaponTooltip,
		"[[Category:Proc Items]]",
		"weapon proc emits the proc-effect category"
	)
	assertContains(charm, "[[Category:Charms]]", "charm emits the charm category")
	assertContains(mold, "[[Category:Molds]]", "mold emits the mold category")
	assertContains(
		skillBook,
		"[[Category:Skill Books]]",
		"skill book emits the skill book category"
	)
	assertContains(
		spellScroll,
		"[[Category:Spell Scrolls]]",
		"spell scroll emits the spell scroll category"
	)

	local link = Item.renderLink({ item = "Ember Longsword" }, "Any Page")
	assertContains(link, "[[Ember Longsword]]", "manual link defaults to item page")
	assertContains(link, "[[File:Ember Longsword.png", "manual link defaults image")

	local stableKeyLink = Item.renderLink({ stablekey = "item:abyssal_plate" }, "Ember Longsword")
	assertContains(stableKeyLink, "[[Abyssal Plate]]", "stable key link uses generated page")
	assertContains(
		stableKeyLink,
		"[[File:Abyssal Plate.png",
		"stable key link uses generated image"
	)

	local imageOnly = Item.renderLink({ item = "Ember Longsword", imageonly = "yes" }, "Any Page")
	assertContains(imageOnly, "[[File:Ember Longsword.png", "image-only link keeps image")
	if string.find(imageOnly, "[[Ember Longsword", 1, true) ~= nil then
		error("image-only link must not append a text link", 2)
	end

	assertEqual(
		Item.fieldValue({}, "Unknown Prototype", "name"),
		"",
		"missing item fields are blank"
	)
	local missing = Item.statusText({}, "Unknown Prototype")
	assertContains(missing, "Missing item data: Unknown Prototype", "missing item is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor item data]]",
		"missing item is tracked"
	)

	return "PASS Erenshor Item testcases"
end

return p

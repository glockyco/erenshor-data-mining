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
		"1g 25s",
		"field buy formats currency"
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

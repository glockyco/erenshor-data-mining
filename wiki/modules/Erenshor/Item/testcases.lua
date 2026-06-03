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

	local infobox = Item.renderInfobox({ stablekey = "item:ember_longsword" }, "Ember Longsword")
	assertContains(infobox, "Ember Longsword", "infobox contains name")
	assertContains(infobox, "18", "infobox contains damage")
	assertContains(infobox, "1g 25s", "infobox formats currency")

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
	local consumable = Item.renderInfobox({ stablekey = "item:healing_draught" }, "Healing Draught")
	assertContains(consumable, "Yes", "consumable boolean renders as human text")

	local nonConsumable = Item.renderInfobox(
		{ stablekey = "item:healing_draught", disposable = "no" },
		"Healing Draught"
	)
	assertContains(nonConsumable, "No", "disposable false override renders as human text")

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

	local missing = Item.renderInfobox({}, "Unknown Prototype")
	assertContains(missing, "Missing item data: Unknown Prototype", "missing item is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor item data]]",
		"missing item is tracked"
	)

	return "PASS Erenshor Item testcases"
end

return p

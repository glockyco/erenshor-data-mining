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
	assertEqual(pageWeapon.stableKey, "item:ember_longsword", "page title resolves item")

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

	local consumable = Item.renderInfobox({ stablekey = "item:healing_draught" }, "Healing Draught")
	assertContains(consumable, "Yes", "consumable boolean renders as human text")

	local nonConsumable = Item.renderInfobox(
		{ stablekey = "item:healing_draught", disposable = "no" },
		"Healing Draught"
	)
	assertContains(nonConsumable, "No", "disposable false override renders as human text")

	local link = Item.renderLink({ item = "Ember Longsword" }, "Any Page")
	assertContains(link, "[[Ember Longsword]]", "link defaults to item page")
	assertContains(link, "[[File:Ember Longsword.png", "link defaults image")

	local positionalLink = Item.renderLink({ [1] = "Abyssal Plate" }, "Ember Longsword")
	assertContains(
		positionalLink,
		"[[Abyssal Plate]]",
		"positional item target wins over current page title"
	)
	assertContains(
		positionalLink,
		"[[File:Abyssal Plate.png",
		"positional item image wins over current page title"
	)

	local crossPageLink = Item.renderLink({ item = "Abyssal Plate" }, "Ember Longsword")
	assertContains(
		crossPageLink,
		"[[Abyssal Plate]]",
		"explicit item name wins over current page title"
	)
	assertContains(
		crossPageLink,
		"[[File:Abyssal Plate.png",
		"explicit item image wins over current page title"
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

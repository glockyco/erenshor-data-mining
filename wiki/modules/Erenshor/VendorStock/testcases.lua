local VendorStock = require("Module:Erenshor/VendorStock")

local p = {}

local CATEGORY = "[[Category:Pages with missing Erenshor vendor stock data]]"

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
		error(
			string.format("%s: expected output to contain %s, got %s", label, expected, actual),
			2
		)
	end
end

local function assertNotContains(actual, unexpected, label)
	if string.find(actual, unexpected, 1, true) ~= nil then
		error(string.format("%s: expected output not to contain %s", label, unexpected), 2)
	end
end

function p.run()
	local stock = VendorStock.render({ stablekey = "character:captain_rowan" })
	assertContains(stock, "|+ Store inventory", "stock caption")
	assertContains(
		stock,
		"! Item name !! Item type !! Price !! Unlock condition",
		"header with the unlock column"
	)
	assertContains(
		stock,
		'data-erenshor-key="item:healing_draught"',
		"item rendered through the link module"
	)
	assertContains(
		stock,
		"[[Weapons|Weapon]] || 120 || Complete ",
		"typed, priced row with its unlock quest"
	)
	assertContains(
		stock,
		'data-erenshor-key="quest:magical_sword"',
		"unlock quest rendered through the link module"
	)
	assertContains(stock, "General || 10 || \n", "kind without a page and no condition")
	assertNotContains(stock, CATEGORY, "a vendor with stock is not tracked")
	local first = string.find(stock, "item:healing_draught", 1, true)
	local last = string.find(stock, "item:ember_longsword", 1, true)
	assertEqual(first < last, true, "rows keep the order of the data")

	-- Each render numbers its TemplateStyles strip markers anew.
	local function withoutMarkers(text)
		return (string.gsub(text, "UNIQ%-%-[%w%-]+%-QINU", ""))
	end
	assertEqual(
		withoutMarkers(VendorStock.render({ page = "Captain Rowan" })),
		withoutMarkers(stock),
		"vendor resolved from its page"
	)

	local shared = VendorStock.render({ page = "Dire Wolf" })
	assertContains(
		shared,
		"character:dire_wolf_alpha, character:dire_wolf_young",
		"shared page lists its characters"
	)
	assertContains(shared, CATEGORY, "shared page is tracked")

	local unknown = VendorStock.render({ page = "No Such Erenshor Page" })
	assertContains(unknown, "No vendor has the page No Such Erenshor Page", "page without a vendor")
	assertContains(unknown, CATEGORY, "page without a vendor is tracked")

	local missing = VendorStock.render({ stablekey = "character:dire_wolf_alpha" })
	assertContains(
		missing,
		"Missing vendor stock data: character:dire_wolf_alpha",
		"character without stock"
	)
	assertContains(missing, CATEGORY, "character without stock is tracked")

	return "PASS Erenshor VendorStock testcases"
end

return p

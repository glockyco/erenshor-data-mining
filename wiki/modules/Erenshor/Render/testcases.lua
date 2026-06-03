local Render = require("Module:Erenshor/Render")

local p = {}

local function assertEqual(actual, expected, label)
	if actual ~= expected then
		error(
			string.format("%s: expected %s, got %s", label, tostring(expected), tostring(actual)),
			2
		)
	end
end

function p.run()
	assertEqual(
		Render.infobox({
			title = "Sword of Flames",
			classes = { "itembox" },
			rows = {
				{ label = "Damage", value = 18 },
				{ label = "Classes", value = "[[Warrior]] / [[Paladin]]" },
				{ label = "Empty", value = "" },
			},
		}),
		'<table class="infobox erenshor-infobox itembox"><caption>Sword of Flames</caption><tr><th>Damage</th><td>18</td></tr><tr><th>Classes</th><td>[[Warrior]] / [[Paladin]]</td></tr></table>',
		"infobox renders deterministic non-empty rows"
	)
	assertEqual(
		Render.table({
			classes = { "wikitable", "sortable" },
			headers = { "Name", "Damage" },
			rows = {
				{ "Sword", 18 },
				{ "Axe", 12 },
			},
		}),
		'<table class="wikitable sortable"><tr><th>Name</th><th>Damage</th></tr><tr><td>Sword</td><td>18</td></tr><tr><td>Axe</td><td>12</td></tr></table>',
		"table renders headers and rows deterministically"
	)

	return "PASS Erenshor Render testcases"
end

return p

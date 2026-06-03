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

local function assertContains(actual, needle, label)
	if not tostring(actual):find(needle, 1, true) then
		error(string.format("%s: expected %s to contain %s", label, tostring(actual), needle), 2)
	end
end

function p.run()
	local infobox = Render.infobox({
		title = "Sword of Flames",
		classes = { "itembox" },
		rows = {
			{ label = "Image", value = "[[File:Sword of Flames.png|300px]]" },
			{ label = "Damage", value = 18 },
			{ label = "Classes", value = "[[Warrior]] / [[Paladin]]" },
			{ label = "Empty", value = "" },
		},
		sections = {
			{
				title = "Base Stats",
				rows = {
					{ label = "Health", value = 25 },
				},
				groups = {
					{
						kind = "horizontal",
						rows = {
							{ label = "Magic", value = 4 },
							{ label = "Poison", value = 5 },
						},
					},
				},
			},
		},
	})
	assertContains(infobox, '<div class="portable-infobox', "infobox renders portable shell")
	assertContains(infobox, "pi-type-itembox", "infobox includes type class")
	assertContains(
		infobox,
		'<div class="pi-item pi-item-spacing pi-title"',
		"infobox renders title"
	)
	assertContains(
		infobox,
		'<div class="pi-item pi-media pi-image"',
		"infobox renders image as media"
	)
	assertContains(infobox, 'data-source="Damage"', "infobox renders row source")
	assertContains(
		infobox,
		'<div class="pi-data-label pi-secondary-font">Damage:</div>',
		"infobox renders label"
	)
	assertContains(infobox, '<div class="pi-data-value pi-font">18</div>', "infobox renders value")
	assertContains(infobox, "Base Stats", "infobox renders section headers")
	assertContains(
		infobox,
		'<table class="pi-horizontal-group"><tr>',
		"infobox renders horizontal groups"
	)
	assertContains(
		infobox,
		'<th class="pi-horizontal-group-item pi-data-label pi-secondary-font pi-border-color pi-item-spacing" data-source="Magic">Magic:</th>',
		"infobox renders horizontal labels"
	)
	assertContains(
		infobox,
		'<td class="pi-horizontal-group-item pi-data-value pi-font pi-border-color pi-item-spacing" data-source="Poison">5</td>',
		"infobox renders horizontal values"
	)
	if infobox:find("Empty", 1, true) then
		error("empty rows are omitted", 2)
	end
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

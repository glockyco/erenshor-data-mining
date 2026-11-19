local Format = require("Module:Erenshor/Format")

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
		Format.escape("A&B <Sword>"),
		"A&amp;B &lt;Sword&gt;",
		"escape encodes HTML-sensitive text"
	)
	assertEqual(
		Format.pageLink("Sword of Flames"),
		"[[Sword of Flames]]",
		"page link without label"
	)
	assertEqual(
		Format.pageLink("Sword of Flames", "Sword"),
		"[[Sword of Flames|Sword]]",
		"page link with label"
	)
	assertEqual(
		Format.classList({ "Warrior", "Paladin" }),
		"[[Warrior]] / [[Paladin]]",
		"class list links classes"
	)
	assertEqual(
		Format.classSpans(" Bard, Windblade "),
		'<span class="item-tooltip-class">Bard</span><span class="item-tooltip-class">Windblade</span>',
		"class names render with the existing restriction markup"
	)
	assertEqual(
		Format.classSpans({ args = { "Bard, A&B" } }),
		'<span class="item-tooltip-class">Bard</span><span class="item-tooltip-class">A&amp;B</span>',
		"class span invoke entry point escapes display names"
	)
	assertEqual(Format.classSpans(""), "", "blank class restrictions render no spans")
	assertEqual(
		Format.classLevelRows(" Bard: 5, Windblade: 7 "),
		'<div class="item-tooltip-book-class-req">Bard: 5</div>'
			.. '<div class="item-tooltip-book-class-req">Windblade: 7</div>',
		"class level pairs render with the existing book markup"
	)
	assertEqual(
		Format.classLevelRows({ args = { "A&B: 3" } }),
		'<div class="item-tooltip-book-class-req">A&amp;B: 3</div>',
		"class level invoke entry point escapes display names"
	)
	assertEqual(Format.classLevelRows(nil), "", "blank class levels render no rows")
	assertEqual(
		Format.classBand({ args = { "", "Bard: 1, Druid: 1" } }),
		'<div class="item-tooltip-classes"><span class="item-tooltip-class">Bard</span>'
			.. '<span class="item-tooltip-class">Druid</span></div>',
		"the level input supplies class names when no list is given"
	)
	assertEqual(
		Format.bookLevels({ args = { "Bard: 1, Druid: 1", "scroll" } }),
		'<div class="item-tooltip-book-requirement">Required Level: 1</div>',
		"a shared scroll level renders once"
	)
	local unequal = "Arcanist: 8, Stormcaller: 16"
	assertEqual(
		Format.bookLevels({ args = { unequal, "scroll" } }),
		'<div class="item-tooltip-book-requirement">Required Level:</div>'
			.. '<div class="item-tooltip-book-class-requirements">'
			.. Format.classLevelRows(unequal)
			.. "</div>",
		"unequal scroll levels remain separate"
	)
	assertEqual(
		Format.bookLevels({ args = { "Bard: 1" } }),
		'<div class="item-tooltip-book-requirement">REQUIRED LEVEL:</div>'
			.. '<div class="item-tooltip-book-class-requirements">'
			.. '<div class="item-tooltip-book-class-req">Bard: 1</div></div>',
		"skill books keep class-specific rows"
	)
	for _, invalid in ipairs({ "Bard", "Bard: 0", "Bard: -1", "Bard: nope", ": 3" }) do
		if pcall(Format.classLevelRows, invalid) then
			error("Accepted an invalid class level pair: " .. invalid)
		end
	end
	assertEqual(Format.currency(12345), "12345", "currency renders the raw gold value")
	assertEqual(Format.currency(50), "50", "currency renders the raw gold value")
	assertEqual(Format.signedStat(5), "+5", "positive stat includes sign")
	assertEqual(Format.signedStat(-3), "-3", "negative stat keeps sign")
	assertEqual(Format.resistLabel("fire"), "Fire Resist", "resist labels are title-cased")
	assertEqual(Format.seconds(1), "1 second", "one second is singular")
	assertEqual(Format.seconds(9), "9 seconds", "whole seconds have no decimals")
	assertEqual(Format.seconds(13.33), "13.33 seconds", "fractional seconds keep their decimals")
	assertEqual(
		Format.categories({ "Items", "Weapons" }),
		"[[Category:Items]][[Category:Weapons]]",
		"categories concatenate"
	)

	return "PASS Erenshor Format testcases"
end

return p

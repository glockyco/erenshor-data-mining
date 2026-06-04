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
		Format.fileLink("Sword.png", { alt = "Sword of Flames", size = "32x32px" }),
		"[[File:Sword.png|32x32px|alt=Sword of Flames]]",
		"file link includes size and alt text"
	)
	assertEqual(
		Format.classList({ "Warrior", "Paladin" }),
		"[[Warrior]] / [[Paladin]]",
		"class list links classes"
	)
	assertEqual(Format.currency(12345), "12345", "currency renders the raw gold value")
	assertEqual(Format.currency(50), "50", "currency renders the raw gold value")
	assertEqual(Format.signedStat(5), "+5", "positive stat includes sign")
	assertEqual(Format.signedStat(-3), "-3", "negative stat keeps sign")
	assertEqual(Format.resistLabel("fire"), "Fire Resist", "resist labels are title-cased")
	assertEqual(
		Format.categories({ "Items", "Weapons" }),
		"[[Category:Items]][[Category:Weapons]]",
		"categories concatenate"
	)

	return "PASS Erenshor Format testcases"
end

return p

local TreasureGuardian = require("Module:Erenshor/TreasureGuardian")

local p = {}

local function assertContains(text, expected, label)
	if not string.find(text, expected, 1, true) then
		error(string.format("%s: expected %q in %q", label, expected, text), 2)
	end
end

function p.run(frame)
	local horror = TreasureGuardian.render({ stablekey = "character:ancient horror" })
	assertContains(
		horror,
		"the ground rumbles for 5 seconds. Then 3 or 4 guardians appear, chosen at random from "
			.. "[[Ancient Demon]], [[Ancient Horror]], and [[Ancient Skeleton]].",
		"wave text"
	)
	assertContains(
		horror,
		"never before 3 waves have appeared, and then with a chance of 30% after 3 waves, 60% after 4 waves, "
			.. "90% after 5 waves, and 100% after 6 waves, even while guardians are alive.",
		"break chances"
	)
	assertContains(
		horror,
		"| 1 || 2–4 || 858 || 3 || 2.45 s || 30–60 || 2–4",
		"player level 1 row"
	)
	assertContains(
		horror,
		"| 35 || 31–36 || 72,800–163,800 || 53–59 || 1.9–1.97 s || 465–540 || 16–43",
		"level 35 row"
	)

	local missing = TreasureGuardian.render({ stablekey = "character:not a guardian" })
	assertContains(
		missing,
		"Missing treasure guardian data: character:not a guardian",
		"unknown key"
	)
	return "PASS Erenshor TreasureGuardian testcases"
end

return p

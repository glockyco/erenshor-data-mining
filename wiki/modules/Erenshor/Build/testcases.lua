local Build = require("Module:Erenshor/Build")

local p = {}

local function assertEqual(actual, expected, label)
	if actual ~= expected then
		error(
			string.format("%s: expected %s, got %s", label, tostring(expected), tostring(actual)),
			2
		)
	end
end

function p.run(frame)
	assertEqual(Build.id(frame), "24405256", "build ID")
	assertEqual(Build.published(frame), "2026-07-27", "published date")
	assertEqual(Build.text(frame), "build 24405256 (published 2026-07-27)", "build text")
	return "PASS Erenshor Build testcases"
end

return p

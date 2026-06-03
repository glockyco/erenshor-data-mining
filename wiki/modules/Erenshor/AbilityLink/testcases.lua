local AbilityLink = require("Module:Erenshor/AbilityLink")

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

local function assertNotContains(actual, unexpected, label)
	if string.find(actual, unexpected, 1, true) ~= nil then
		error(string.format("%s: expected output not to contain %s", label, unexpected), 2)
	end
end

function p.run()
	local resolved = AbilityLink.resolve({ "Minor Lightning" })
	assertEqual(resolved.page, "Minor Lightning", "page defaults from generated spell data")
	assertEqual(resolved.name, "Minor Lightning", "text defaults from generated spell data")
	assertEqual(resolved.image, "Minor Lightning", "image defaults from generated spell data")

	local stance = AbilityLink.resolve({ "Aggressive" })
	assertEqual(stance.page, "Aggressive Stance", "display name can resolve a stance page")

	local override = AbilityLink.resolve({
		"Minor Lightning",
		image = "Manual.png",
		link = "Manual Link",
		text = "Manual Text",
	})
	assertEqual(override.page, "Manual Link", "link override wins")
	assertEqual(override.name, "Manual Text", "text override wins")
	assertEqual(override.image, "Manual.png", "image override wins")

	local unknown = AbilityLink.resolve({ "Prototype Ability" })
	assertEqual(unknown.page, "Prototype Ability", "unknown target falls back to target page")
	assertEqual(unknown.name, "Prototype Ability", "unknown target falls back to target text")

	local rendered = AbilityLink.render({ "Minor Lightning" })
	assertContains(
		rendered,
		"[[File:Minor Lightning.png|30px|link=Minor Lightning]]",
		"rendered link contains image"
	)
	assertContains(rendered, "[[Minor Lightning]]", "rendered link contains page link")

	local imageOnly = AbilityLink.render({ "Minor Lightning", imageonly = "1" })
	assertContains(
		imageOnly,
		"[[File:Minor Lightning.png|30px|link=Minor Lightning]]",
		"image-only link contains image"
	)
	assertNotContains(imageOnly, "[[Minor Lightning]]", "image-only link hides text")

	return "PASS Erenshor AbilityLink testcases"
end

return p

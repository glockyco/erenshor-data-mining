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
	local resolved = AbilityLink.resolve({ stablekey = "spell:minor_lightning" })
	assertEqual(resolved.state, "resolved", "keyed ability resolves")
	assertEqual(
		resolved.requestedKey,
		"spell:minor_lightning",
		"ability resolver retains requested key"
	)
	assertEqual(
		resolved.resolvedKey,
		"spell:minor_lightning",
		"ability resolver returns resolved key"
	)
	assertEqual(resolved.page, "Minor Lightning", "page defaults from generated spell data")
	assertEqual(resolved.text, "Minor Lightning", "text defaults from generated spell data")
	assertEqual(resolved.image, "Minor Lightning", "image defaults from generated spell data")

	local manual = AbilityLink.resolve({ "Aggressive" })
	assertEqual(manual.state, "manual", "positional ability remains manual")
	assertEqual(manual.page, "Aggressive", "positional target is a page link, not entity lookup")
	assertEqual(manual.text, "Aggressive", "positional target supplies manual text")

	local stance = AbilityLink.resolve({ stablekey = "stance:aggressive" })
	assertEqual(stance.state, "resolved", "stance key resolves through shared catalog")
	assertEqual(stance.resolvedKey, "stance:aggressive", "stance key remains stable")
	assertEqual(stance.page, "Stance: Aggressive", "stable key can resolve generated stance page")

	local override = AbilityLink.resolve({
		stablekey = "spell:minor_lightning",
		image = "Manual.png",
		link = "Manual Link",
		text = "Manual Text",
	})
	assertEqual(override.page, "Manual Link", "link override wins")
	assertEqual(override.text, "Manual Text", "text override wins")
	assertEqual(override.image, "Manual.png", "image override wins")

	local unknown = AbilityLink.resolve({ "Prototype Ability" })
	assertEqual(unknown.state, "manual", "unknown positional target remains manual")
	assertEqual(unknown.page, "Prototype Ability", "unknown target falls back to target page")
	assertEqual(unknown.text, "Prototype Ability", "unknown target falls back to target text")

	local rendered = AbilityLink.render({ stablekey = "spell:minor_lightning" })
	assertContains(
		rendered,
		"erenshor-link erenshor-link--ability",
		"rendered link has semantic wrapper"
	)
	assertContains(rendered, 'data-erenshor-kind="ability"', "rendered link has kind data")
	assertContains(
		rendered,
		"[[File:Minor Lightning.png|24x24px|link=Minor Lightning]]",
		"rendered link contains image"
	)
	assertContains(rendered, "[[Minor Lightning]]", "rendered link contains page link")

	local imageOnly = AbilityLink.render({ stablekey = "spell:minor_lightning", imageonly = "1" })
	assertContains(imageOnly, "erenshor-link--ability", "image-only link has semantic wrapper")
	assertContains(
		imageOnly,
		"[[File:Minor Lightning.png|24x24px|link=Minor Lightning]]",
		"image-only link contains image"
	)
	assertNotContains(imageOnly, "[[Minor Lightning]]", "image-only link hides text")

	return "PASS Erenshor AbilityLink testcases"
end

return p

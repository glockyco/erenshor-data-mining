local Link = require("Module:Erenshor/Link")

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

-- Expose observations, not expected results, to the Python host parity tests.
function p.probe(frame)
	local args = {}
	for key, value in pairs(frame.args) do
		args[key] = value
	end
	local result = Link.resolve(args.kind, args)
	result.record = nil
	result.rendered = Link.render(args)
	local target = result.page and mw.title.new(result.page)
	result.targetIdentity = target and target.fullText or nil
	return "<pre>" .. mw.text.nowiki(mw.text.jsonEncode(result)) .. "</pre>"
end

function p.catalog()
	local records = {}
	for _, record in pairs(mw.loadData("Module:Erenshor/Data/Links").byKey) do
		table.insert(records, record)
	end
	table.sort(records, function(left, right)
		return left.key < right.key
	end)
	return "<pre>" .. mw.text.nowiki(mw.text.jsonEncode(records)) .. "</pre>"
end

function p.run()
	assertEqual(
		Link.resolve("item", { [1] = "Priel Note (1)" }).state,
		"manual",
		"an entity name is not a page alias"
	)
	assertEqual(
		Link.resolve("item", { [1] = "Abyssal Plate" }).resolvedKey,
		"item:chest - 38 - abyssal plate",
		"a name on another page does not make this page ambiguous"
	)
	assertEqual(
		Link.resolve("item", { [1] = "Different Image Fixture" }).state,
		"ambiguous",
		"entities on one page with different images still need an identity"
	)
	local item = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		stableKey = "item:chest - 38 - abyssal plate",
	})
	assertContains(item, "erenshor-link erenshor-link--item", "item link has semantic class")
	assertContains(item, 'data-erenshor-page="Abyssal Plate"', "item link has target page data")
	assertContains(
		item,
		'data-erenshor-key="item:chest - 38 - abyssal plate"',
		"item link has stable key data"
	)
	assertContains(
		item,
		"[[File:Abyssal Plate icon.png|24x24px|alt=Abyssal Plate|link=Abyssal Plate]]",
		"item link has icon"
	)
	assertContains(item, 'class="erenshor-icon erenshor-icon--item"', "item link draws item slot")
	assertContains(item, "top:1px", "24 px item link has one pixel ring")

	local itemFacts = Link.itemRecord("item:abyssal_plate")
	assertEqual(itemFacts.page, "Abyssal Plate", "itemRecord retains item shard facts")

	local stableKeyOnlyItem = Link.render({
		kind = "item",
		stablekey = "item:chest - 38 - abyssal plate",
	})
	assertContains(stableKeyOnlyItem, "[[Abyssal Plate]]", "stable-key-only item resolves its page")
	assertContains(
		stableKeyOnlyItem,
		"[[File:Abyssal Plate icon.png|24x24px|alt=Abyssal Plate|link=Abyssal Plate]]",
		"stable-key-only item resolves its image"
	)

	local sharedPageItem = Link.render({
		kind = "item",
		page = "Priel Note",
		text = "Priel Note (1)",
	})
	assertContains(
		sharedPageItem,
		"[[File:Priel Note icon.png",
		"items that share a page and an icon show that icon"
	)
	assertNotContains(
		sharedPageItem,
		"[[Category:Pages with ambiguous Erenshor links]]",
		"items that share a page and an icon are not tracked"
	)
	assertNotContains(
		sharedPageItem,
		"[[File:Priel Note (1).png",
		"item link does not invent an image from disambiguated text"
	)

	local sharedPageAbility = Link.render({ kind = "ability", [1] = "Flame Bolt" })
	assertNotContains(sharedPageAbility, "[[File:", "ambiguous ability has no invented icon")
	assertContains(
		sharedPageAbility,
		"[[Category:Pages with ambiguous Erenshor links]]",
		"abilities that share a page are tracked, because their tooltips need a key"
	)
	assertContains(item, "[[Abyssal Plate]]", "item link has page link")

	local function iconFrame(args, parent)
		return {
			args = args,
			getParent = function()
				return { args = parent or {} }
			end,
		}
	end
	assertEqual(
		Link.icon(iconFrame({ item = "Abyssal Plate" })),
		"Abyssal Plate icon.png",
		"slot resolves an item name"
	)
	assertEqual(
		Link.icon(iconFrame({ stablekey = "item:chest - 38 - abyssal plate" })),
		"Abyssal Plate icon.png",
		"slot resolves an item key"
	)
	assertEqual(
		Link.icon(iconFrame({ image = "Manual.webp" }, { item = "Abyssal Plate" })),
		"Manual.webp",
		"slot override is a full title"
	)
	assertEqual(
		Link.icon(iconFrame({ item = "Unknown Item" })),
		"",
		"unknown slot has no invented icon"
	)
	for _, kind in ipairs({ "item", "ability" }) do
		local noIcon = Link.render({ kind = kind, page = "Unknown Target" })
		assertNotContains(noIcon, "[[File:", "unknown link has no invented icon")
		assertNotContains(noIcon, "erenshor-icon", "unknown link draws no icon frame")
		assertContains(noIcon, "[[Unknown Target]]", "unknown link still shows its text")
		assertNotContains(
			Link.render({ kind = kind, page = "Unknown Target", imageonly = "1" }),
			"[[File:",
			"icon-only missing picture draws no file"
		)
	end

	local keyed = Link.resolve("item", { stablekey = "item:chest - 38 - abyssal plate" })
	assertEqual(keyed.state, "resolved", "explicit key resolves")
	assertEqual(
		keyed.requestedKey,
		"item:chest - 38 - abyssal plate",
		"resolver retains requested key"
	)
	assertEqual(
		keyed.resolvedKey,
		"item:chest - 38 - abyssal plate",
		"resolver returns resolved key"
	)
	assertEqual(keyed.page, "Abyssal Plate", "keyed resolver returns canonical page")
	assertEqual(keyed.text, "Abyssal Plate", "keyed resolver returns canonical text")

	local positionalKinds = {
		{ kind = "item", page = "Abyssal Plate", key = "item:chest - 38 - abyssal plate" },
		{ kind = "ability", page = "Minor Lightning", key = "spell:minor_lightning" },
		{ kind = "character", page = "A Grizzly Bear", key = "character:a_grizzly_bear" },
		{ kind = "quest", page = "A Hermit's Request", key = "quest:a hermit's request" },
		{ kind = "zone", page = "Blacksalt Strand", key = "zone:saltedstrand" },
		{ kind = "faction", page = "The Followers of Evil", key = "faction:evil" },
		{ kind = "class", page = "Windblade", key = "class:duelist" },
	}
	for _, candidate in ipairs(positionalKinds) do
		local positionalResult = Link.resolve(candidate.kind, { [1] = candidate.page })
		assertEqual(
			positionalResult.state,
			"resolved",
			"unique positional " .. candidate.kind .. " enriches"
		)
		assertEqual(
			positionalResult.page,
			candidate.page,
			"positional " .. candidate.kind .. " retains page"
		)
		assertEqual(
			positionalResult.resolvedKey,
			candidate.key,
			"positional " .. candidate.kind .. " receives identity"
		)

		local positionalRendered = Link.render({ kind = candidate.kind, [1] = candidate.page })
		assertContains(
			positionalRendered,
			"[[" .. candidate.page .. "]]",
			"positional " .. candidate.kind .. " retains navigable link"
		)
		assertContains(
			positionalRendered,
			'data-erenshor-key="' .. candidate.key .. '"',
			"positional " .. candidate.kind .. " emits enriched identity"
		)
	end

	local sharedPositionalItem = Link.resolve("item", { [1] = "Priel Note" })
	assertEqual(
		sharedPositionalItem.state,
		"shared",
		"items on one page with one icon resolve to the page"
	)
	assertEqual(sharedPositionalItem.resolvedKey, nil, "a shared page gives no identity")
	assertEqual(sharedPositionalItem.image, "Priel Note icon.png", "a shared page keeps its icon")

	local ambiguousPositionalAbility = Link.resolve("ability", { [1] = "Flame Bolt" })
	assertEqual(
		ambiguousPositionalAbility.state,
		"ambiguous",
		"ambiguous positional page remains ambiguous"
	)
	assertEqual(
		ambiguousPositionalAbility.page,
		"Flame Bolt",
		"ambiguous positional page remains navigable"
	)
	local ambiguousPositionalRendered = Link.render({ kind = "ability", [1] = "Flame Bolt" })
	assertContains(
		ambiguousPositionalRendered,
		"[[Flame Bolt]]",
		"ambiguous positional page keeps its navigable link"
	)
	assertContains(
		ambiguousPositionalRendered,
		"[[Category:Pages with ambiguous Erenshor links]]",
		"ambiguous positional page is tracked"
	)

	local positional = Link.resolve("zone", { "Blacksalt Strand" })
	assertEqual(positional.page, "Blacksalt Strand", "positional page remains unchanged")
	assertEqual(positional.text, "Blacksalt Strand", "positional text remains unchanged")
	assertEqual(positional.state, "resolved", "unique positional page is enriched")
	assertEqual(
		positional.resolvedKey,
		"zone:saltedstrand",
		"unique positional page receives identity"
	)

	local keyedPositional = Link.resolve("ability", {
		[1] = "Legacy Ability Target",
		stablekey = "spell:minor_lightning",
	})
	assertEqual(
		keyedPositional.page,
		"Legacy Ability Target",
		"legacy positional fallback keeps target precedence"
	)
	local keyedPositionalRendered = Link.render({
		kind = "ability",
		[1] = "Legacy Ability Target",
		stablekey = "spell:minor_lightning",
	})
	assertContains(
		keyedPositionalRendered,
		"[[Legacy Ability Target|Minor Lightning]]",
		"legacy positional fallback keeps navigable target"
	)
	assertNotContains(
		keyedPositionalRendered,
		"[[Category:Pages with mismatched Erenshor link targets]]",
		"legacy positional fallback does not count as named mismatch"
	)

	local wrongKind = Link.resolve("ability", { stablekey = "item:chest - 38 - abyssal plate" })
	assertEqual(wrongKind.state, "unresolved", "wrong-kind key is unresolved")

	local unresolved = Link.resolve("ability", {
		stablekey = "spell:does-not-exist",
		link = "Prototype Ability",
		text = "Prototype",
	})
	assertEqual(unresolved.state, "unresolved", "unknown key is unresolved")
	assertEqual(
		unresolved.page,
		"Prototype Ability",
		"unknown key preserves explicit fallback page"
	)
	assertEqual(unresolved.text, "Prototype", "unknown key preserves explicit fallback text")
	local unresolvedRendered = Link.render({ kind = "ability", stablekey = "spell:does-not-exist" })
	assertContains(
		unresolvedRendered,
		'<span class="erenshor-link erenshor-link--unresolved">Unresolved ability link: spell:does-not-exist</span>',
		"unknown key without fallback is visible"
	)
	assertContains(
		unresolvedRendered,
		"[[Category:Pages with unresolved Erenshor links]]",
		"unknown key is tracked"
	)

	local unresolvedFallback = Link.render({
		kind = "ability",
		stablekey = "spell:does-not-exist",
		link = "Prototype Ability",
		text = "Prototype",
	})
	assertContains(
		unresolvedFallback,
		"[[Prototype Ability|Prototype]]",
		"unresolved key keeps explicit fallback link"
	)
	assertContains(
		unresolvedFallback,
		"[[Category:Pages with unresolved Erenshor links]]",
		"unresolved fallback remains tracked"
	)

	local mismatch = Link.render({
		kind = "ability",
		stablekey = "spell:minor_lightning",
		link = "Manual Ability Target",
		text = "Manual Ability",
	})
	assertContains(
		mismatch,
		"[[Manual Ability Target|Manual Ability]]",
		"mismatch preserves target override"
	)
	assertContains(
		mismatch,
		"[[Category:Pages with mismatched Erenshor link targets]]",
		"mismatch is tracked"
	)
	assertNotContains(item, 'data-erenshor-quality="', "item link omits quality by default")
	assertNotContains(
		item,
		'data-erenshor-quality="Standard"',
		"item link does not invent Standard metadata by default"
	)

	local standardItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		quality = "Standard",
	})
	assertContains(
		standardItem,
		'data-erenshor-quality="Standard"',
		"item link emits explicit Standard quality metadata"
	)
	assertNotContains(
		standardItem,
		'data-erenshor-quality="Normal"',
		"item link does not emit legacy Normal quality metadata"
	)

	local blessedItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		quality = "blessed",
	})
	assertContains(
		blessedItem,
		'data-erenshor-quality="Blessed"',
		"item link emits canonical Blessed quality"
	)

	local normalizedQualityItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Abyssal Plate",
		quality = "  iMpRoVeD +3  ",
	})
	assertContains(
		normalizedQualityItem,
		'data-erenshor-quality="Improved +3"',
		"item link normalizes quality case and whitespace"
	)

	for _, invalidQuality in ipairs({ "Normal", "normal", "0" }) do
		local rejected, rejectionError = pcall(function()
			Link.render({ kind = "item", page = "Abyssal Plate", quality = invalidQuality })
		end)
		if rejected then
			error("legacy item quality alias must fail fast: " .. invalidQuality, 2)
		end
		assertContains(
			rejectionError,
			"quality",
			"legacy item quality alias identifies parameter: " .. invalidQuality
		)
	end

	local invalidQualityOk, invalidQualityError = pcall(function()
		Link.render({ kind = "item", page = "Abyssal Plate", quality = "Mythic" })
	end)
	if invalidQualityOk then
		error("invalid item quality must fail fast", 2)
	end
	assertContains(invalidQualityError, "quality", "invalid item quality identifies parameter")
	assertContains(invalidQualityError, "invalid", "invalid item quality identifies invalid value")

	local stableKeyQualityItem = Link.render({
		kind = "item",
		page = "Abyssal Plate",
		text = "Duplicate-page item",
		stableKey = "item:chest - 38 - abyssal plate",
		quality = " Blessed ",
	})
	assertContains(
		stableKeyQualityItem,
		'data-erenshor-key="item:chest - 38 - abyssal plate"',
		"item link preserves stable key with quality"
	)
	assertContains(
		stableKeyQualityItem,
		'data-erenshor-quality="Blessed"',
		"item link emits quality with stable key"
	)

	local itemImageOnly = Link.render({ kind = "item", page = "Abyssal Plate", imageonly = "1" })
	assertContains(
		itemImageOnly,
		"[[File:Abyssal Plate icon.png|24x24px|alt=Abyssal Plate|link=Abyssal Plate]]",
		"item image-only has icon"
	)
	assertNotContains(itemImageOnly, "[[Abyssal Plate]]", "item image-only suppresses text")

	local ability = Link.render({ kind = "ability", stableKey = "spell:minor_lightning" })
	assertContains(
		ability,
		"erenshor-link erenshor-link--ability",
		"ability link has semantic class"
	)
	assertContains(
		ability,
		'data-erenshor-page="Minor Lightning"',
		"ability link has target page data"
	)
	assertContains(
		ability,
		'data-erenshor-key="spell:minor_lightning"',
		"ability link has stable key data"
	)
	assertContains(
		ability,
		"[[File:Minor Lightning icon.png|22x22px|link=Minor Lightning]]",
		"ability link has icon inside its border"
	)
	assertContains(
		ability,
		'class="erenshor-icon erenshor-icon--ability"',
		"spell link draws the black border"
	)
	for _, key in ipairs({ "skill:backstab", "stance:aggressive" }) do
		local icon = Link.render({ kind = "ability", stablekey = key })
		assertContains(icon, "erenshor-icon--ability", "skill and stance use the black border")
	end
	assertContains(ability, "[[Minor Lightning]]", "ability link has page link")

	local quest = Link.render({ kind = "quest", page = "Reward Quest" })
	assertContains(quest, "erenshor-link erenshor-link--quest", "quest link has semantic class")
	assertNotContains(quest, "[[File:", "quest link has no synthetic icon")
	assertContains(quest, "[[Reward Quest]]", "quest link has page link")
	local legacyQuest = Link.render({ kind = "quest", questlink = "Reward Quest" })
	assertContains(legacyQuest, "[[Reward Quest]]", "legacy questlink parameter links its page")

	local character = Link.render({ kind = "character", page = "A Grizzly Bear" })
	assertContains(
		character,
		"erenshor-link erenshor-link--character",
		"character link has semantic class"
	)
	assertContains(character, "[[A Grizzly Bear]]", "character link has page link")
	assertContains(
		character,
		'data-erenshor-page="A Grizzly Bear"',
		"character link has target page data"
	)

	local punctuation = Link.render({ kind = "zone", page = "R&D <Elite>" })
	assertContains(
		punctuation,
		'data-erenshor-page="R&amp;D &lt;Elite&gt;"',
		"target page data escapes HTML-sensitive title"
	)

	local excluded = Link.render({ kind = "item", page = "-", text = "-" })
	assertNotContains(excluded, "erenshor-link", "plain excluded text has no semantic wrapper")

	local zone = Link.render({ kind = "zone", page = "Blacksalt Strand" })
	assertContains(zone, "erenshor-link erenshor-link--zone", "zone link has semantic class")
	assertContains(zone, "[[Blacksalt Strand]]", "zone link has page link")

	local faction = Link.render({ kind = "faction", page = "The Followers of Good" })
	assertContains(
		faction,
		"erenshor-link erenshor-link--faction",
		"faction link has semantic class"
	)
	assertContains(faction, "[[The Followers of Good]]", "faction link has page link")

	local class = Link.render({ kind = "class", page = "Duelist" })
	assertContains(class, "erenshor-link erenshor-link--class", "class link has semantic class")
	assertContains(class, "[[Duelist]]", "class link has page link")

	local keyedKinds = {
		{ kind = "item", key = "item:chest - 38 - abyssal plate" },
		{ kind = "ability", key = "spell:minor_lightning" },
		{ kind = "character", key = "character:a_grizzly_bear" },
		{ kind = "quest", key = "quest:a hermit's request" },
		{ kind = "zone", key = "zone:saltedstrand" },
		{ kind = "faction", key = "faction:evil" },
		{ kind = "class", key = "class:duelist" },
	}
	for _, candidate in ipairs(keyedKinds) do
		local result = Link.resolve(candidate.kind, { stablekey = candidate.key })
		assertEqual(result.state, "resolved", "keyed " .. candidate.kind .. " resolves")
		assertEqual(
			result.resolvedKey,
			candidate.key,
			"keyed " .. candidate.kind .. " retains identity"
		)
	end

	local onePage = Link.pageKeys("item", "Abyssal Plate")
	assertEqual(#onePage, 1, "page keys of a page with one item")
	assertEqual(onePage[1], "item:chest - 38 - abyssal plate", "page key of a page with one item")
	local sharedPage = Link.pageKeys("Character", "Dire Wolf")
	assertEqual(#sharedPage, 2, "page keys of a page that two characters share")
	assertEqual(sharedPage[1], "character:dire_wolf_alpha", "first shared page key")
	assertEqual(sharedPage[2], "character:dire_wolf_young", "second shared page key")
	assertEqual(#Link.pageKeys("zone", "Dire Wolf"), 0, "page keys of another kind")
	assertEqual(#Link.pageKeys("item", "No Such Erenshor Page"), 0, "page keys of an unknown page")
	assertEqual(#Link.pageKeys("unknown", "Abyssal Plate"), 0, "page keys of an unknown kind")
	assertEqual(#Link.pageKeys(nil, "Abyssal Plate"), 0, "page keys without a kind")
	assertEqual(#Link.pageKeys("item", nil), 0, "page keys without a page")
	assertEqual(#Link.pageKeys("item", " \t "), 0, "page keys of a blank page")
	assertEqual(
		Link.pageKeys("ITEM", "  abyssal_Plate  ")[1],
		"item:chest - 38 - abyssal plate",
		"page keys normalize underscores, whitespace and initial case"
	)
	for _, fixture in ipairs({
		{ page = "Minor Lightning", keys = { "spell:minor_lightning" } },
		{ page = "Backstab", keys = { "skill:backstab" } },
		{ page = "Defensive", keys = { "stance:defensive" } },
		{
			page = "Stance: Aggressive",
			keys = { "skill:stance - aggressive", "stance:aggressive" },
		},
		{ page = "Flame Bolt", keys = { "spell:flame_bolt", "spell:flame_bolt_greater" } },
	}) do
		local actual = Link.pageKeys("ABILITY", fixture.page)
		assertEqual(#actual, #fixture.keys, "ability page variant count for " .. fixture.page)
		for index, key in ipairs(fixture.keys) do
			assertEqual(actual[index], key, "ability page variant order for " .. fixture.page)
		end
	end

	local catalog = mw.loadData("Module:Erenshor/Data/Links")
	local kinds = { unknown = true, spell = true, skill = true, stance = true }
	for _, record in pairs(catalog.byKey) do
		kinds[tostring(record.kind):lower()] = true
	end
	for page, indexedKeys in pairs(catalog.byPage) do
		local encoded = mw.loadData("Module:Erenshor/Data/PageKeys")[page]
		assertEqual(type(encoded), "string", "page index uses JSON strings for " .. page)
		local fixtureKeys = mw.text.jsonDecode(encoded)
		local indexedCount = 0
		for index, key in ipairs(indexedKeys) do
			indexedCount = index
			assertEqual(fixtureKeys[index], key, "page index identity order for " .. page)
		end
		assertEqual(#fixtureKeys, indexedCount, "page index coverage for " .. page)
		for kind in pairs(kinds) do
			local expected = {}
			for _, key in ipairs(indexedKeys) do
				local record = catalog.byKey[key]
				local subtype = tostring(record.subtype or ""):lower()
				if
					tostring(record.kind or ""):lower() == kind
					and (
						kind ~= "ability"
						or subtype == "spell"
						or subtype == "skill"
						or subtype == "stance"
					)
				then
					table.insert(expected, record.key)
				end
			end
			local actual = Link.pageKeys(kind, page)
			assertEqual(#actual, #expected, kind .. " page coverage for " .. page)
			for index, key in ipairs(expected) do
				assertEqual(actual[index], key, kind .. " page order for " .. page)
			end
		end
	end
	for page in pairs(mw.loadData("Module:Erenshor/Data/PageKeys")) do
		assertEqual(type(catalog.byPage[page]), "table", "page index has no extra page " .. page)
	end

	return "PASS Erenshor Link testcases"
end

return p

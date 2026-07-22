local Search = require("Module:Erenshor/Link/Search")

local p = {}

local function assertEqual(actual, expected, label)
	if actual ~= expected then
		error(
			string.format("%s: expected %s, got %s", label, tostring(expected), tostring(actual)),
			2
		)
	end
end

local function assertTrue(value, label)
	if not value then
		error(label, 2)
	end
end

local function decode(args)
	return mw.text.jsonDecode(Search.query({ args = args or {} }))
end

local function assertRecordShape(record, label)
	local expected = {
		key = true,
		kind = true,
		subtype = true,
		name = true,
		page = true,
		image = true,
	}
	local count = 0
	for key in pairs(record) do
		assertTrue(expected[key], label .. " has only primitive fields")
		count = count + 1
	end
	assertEqual(count, 6, label .. " has six primitive fields")
	assertEqual(type(record.image), "string", label .. " has a string image primitive")
end

function p.run()
	local short = decode({ q = "a" })
	assertEqual(#short.results, 0, "one-character queries return no results")

	local unknownKind = decode({ q = "Flame%20Bolt", kind = "unknown" })
	assertEqual(#unknownKind.results, 0, "unknown kinds return no results")

	local decoded = decode({ q = "  Flame%20Bolt  ", kind = "abilit%79" })
	assertEqual(decoded.query, "flame bolt", "query is decoded, trimmed, and lowercased")
	assertEqual(#decoded.results, 2, "decoded ability query preserves duplicate names")
	assertEqual(decoded.results[1].key, "spell:flame_bolt", "exact name results sort by key")
	assertEqual(
		decoded.results[2].key,
		"spell:flame_bolt_greater",
		"duplicate ability remains distinct"
	)
	for index, record in ipairs(decoded.results) do
		assertEqual(record.kind, "ability", "kind filter applies to duplicate result " .. index)
		assertRecordShape(record, "duplicate result " .. index)
	end

	local exactKey = decode({ q = "spell%3Aflame_bolt" })
	assertEqual(#exactKey.results, 2, "key prefix query finds both Flame Bolt keys")
	assertEqual(exactKey.results[1].key, "spell:flame_bolt", "exact key outranks key prefix")
	assertEqual(
		exactKey.results[2].key,
		"spell:flame_bolt_greater",
		"key prefix result follows exact key"
	)

	local namePrefix = decode({ q = "Flame" })
	assertEqual(namePrefix.results[1].name, "Flame Bolt", "name prefix ranks matching names")
	assertEqual(#namePrefix.results, 2, "name prefix preserves both duplicate pages")

	local keyPrefix = decode({ q = "spell%3A" })
	assertTrue(#keyPrefix.results > 0, "key prefix returns spell records")
	for index, record in ipairs(keyPrefix.results) do
		assertTrue(
			mw.ustring.sub(record.key, 1, 6) == "spell:",
			"key prefix result " .. index .. " retains the matching key prefix"
		)
	end

	local pagePrefix = decode({ q = "Stance%3A" })
	assertTrue(#pagePrefix.results > 0, "page prefix returns stance pages")
	assertEqual(
		pagePrefix.results[1].page,
		"Stance: Aggressive",
		"page prefix ranks matching pages"
	)

	local substring = decode({ q = "olt" })
	assertEqual(#substring.results, 2, "substring matching returns both Flame Bolt records")

	local class = decode({ q = "Windblade", kind = "class" })
	assertEqual(#class.results, 1, "class kind filter returns the class")
	assertEqual(class.results[1].key, "class:duelist", "class result has stable key")
	assertEqual(class.results[1].kind, "class", "class result has kind")
	assertEqual(class.results[1].subtype, "", "missing subtype is an explicit empty primitive")
	assertEqual(class.results[1].name, "Windblade", "class result has name")
	assertEqual(class.results[1].page, "Windblade", "class result has page")
	assertEqual(class.results[1].image, "", "missing image remains an empty primitive")
	assertRecordShape(class.results[1], "class result")

	local capped = decode({ q = "te" })
	assertEqual(#capped.results, 25, "search results are capped at 25")
	for index, record in ipairs(capped.results) do
		assertRecordShape(record, "capped result " .. index)
	end

	return "PASS Erenshor Link/Search testcases"
end

return p

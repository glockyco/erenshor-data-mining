local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Quality = require("Module:Erenshor/Item/Quality")

local LinkData
local ItemIndex

local p = {}

local ITEM_SHARDS = {}

local UNRESOLVED_CATEGORY = "[[Category:Pages with unresolved Erenshor links]]"
local MISMATCH_CATEGORY = "[[Category:Pages with mismatched Erenshor link targets]]"
local AMBIGUOUS_CATEGORY = "[[Category:Pages with ambiguous Erenshor links]]"

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

local function copyTable(value)
	local out = {}
	if value == nil then
		return out
	end
	for key, item in pairs(value) do
		out[key] = item
	end
	return out
end

local function ensureImageFile(image, fallbackName)
	local value = image
	if isBlank(value) then
		value = fallbackName
	end
	if isBlank(value) then
		return nil
	end
	value = tostring(value)
	if
		value:match("%.[Pp][Nn][Gg]$")
		or value:match("%.[Jj][Pp][Gg]$")
		or value:match("%.[Jj][Pp][Ee][Gg]$")
	then
		return value
	end
	return value .. ".png"
end

local function templateArgs(frame)
	local out = copyTable(Args.parentArgs(frame))
	for key, value in pairs(frame.args or {}) do
		out[key] = value
	end
	return out
end

local function explicitStableKey(args)
	return Args.resolve(args or {}, "stablekey", nil)
		or Args.resolve(args or {}, "stableKey", nil)
		or Args.resolve(args or {}, "key", nil)
end

local function loadItemShard(name)
	if isBlank(name) then
		return nil
	end
	if ITEM_SHARDS[name] == nil then
		ITEM_SHARDS[name] = mw.loadData("Module:Erenshor/Data/Items/" .. tostring(name))
	end
	return ITEM_SHARDS[name]
end

local function itemByStableKey(stableKey)
	if isBlank(stableKey) then
		return nil
	end
	if ItemIndex == nil then
		ItemIndex = mw.loadData("Module:Erenshor/Data/Items")
	end
	local shardName = ItemIndex.byKey[stableKey]
	local shard = loadItemShard(shardName)
	if shard == nil then
		return nil
	end
	return shard[stableKey]
end

local function loadLinkData()
	if LinkData == nil then
		LinkData = mw.loadData("Module:Erenshor/Data/Links")
	end
	return LinkData
end

local function normalizePage(page)
	if isBlank(page) then
		return nil
	end
	local title = mw.title.new(tostring(page))
	if title ~= nil and not isBlank(title.prefixedText) then
		return title.prefixedText
	end
	return tostring(page)
end

local function nowiki(value)
	if mw.text ~= nil and type(mw.text.nowiki) == "function" then
		return mw.text.nowiki(tostring(value))
	end
	return tostring(value)
end

local function warnUnresolved(kind, stableKey)
	if mw.addWarning ~= nil then
		mw.addWarning("Unresolved Erenshor " .. nowiki(kind) .. " link key: " .. nowiki(stableKey))
	end
end

local function warnMismatch(kind, stableKey, suppliedPage, canonicalPage)
	if mw.addWarning ~= nil then
		mw.addWarning(
			"Mismatched Erenshor "
				.. nowiki(kind)
				.. " link target for key "
				.. nowiki(stableKey)
				.. ": "
				.. nowiki(suppliedPage)
				.. " (expected "
				.. nowiki(canonicalPage)
				.. ")"
		)
	end
end

local function kindMatches(kind, record)
	if record == nil then
		return false
	end
	if tostring(record.kind or ""):lower() ~= kind then
		return false
	end
	if kind == "ability" then
		local subtype = tostring(record.subtype or ""):lower()
		return subtype == "spell" or subtype == "skill" or subtype == "stance"
	end
	return true
end

local function keyPrefixMatches(kind, stableKey)
	local prefix = tostring(stableKey):match("^([^:]+):")
	if prefix == nil then
		return false
	end
	prefix = prefix:lower()
	if kind == "ability" then
		return prefix == "spell" or prefix == "skill" or prefix == "stance"
	end
	return prefix == kind
end

local function targetFor(kind, args)
	if kind == "item" then
		return Args.resolve(args, "item", nil)
			or Args.resolve(args, "name", nil)
			or Args.resolve(args, 1, nil)
	end
	return Args.resolve(args, 1, nil)
end

local function explicitPageFor(args)
	return Args.resolve(args, "link", nil) or Args.resolve(args, "page", nil)
end

local function pageMatches(kind, page)
	if isBlank(page) then
		return {}
	end
	local data = loadLinkData()
	local byPage = data.byPage or {}
	local keys = byPage[normalizePage(page)] or {}
	local matches = {}
	for _, stableKey in ipairs(keys) do
		local record = (data.byKey or {})[stableKey]
		if kindMatches(kind, record) then
			table.insert(matches, record)
		end
	end
	return matches
end

local function resolveRecord(kind, requestedKey)
	if isBlank(requestedKey) or not keyPrefixMatches(kind, requestedKey) then
		return nil
	end
	local data = loadLinkData()
	local record = (data.byKey or {})[requestedKey]
	if kindMatches(kind, record) then
		return record
	end
	return nil
end

local function appendCategory(output, category)
	if isBlank(output) then
		return category
	end
	return output .. category
end

local function spanAttributes(kind, args, page, quality, stableKey)
	local attributes = {
		'class="erenshor-link erenshor-link--' .. Format.escape(kind) .. '"',
		'data-erenshor-kind="' .. Format.escape(kind) .. '"',
	}
	if not isBlank(page) then
		table.insert(attributes, 'data-erenshor-page="' .. Format.escape(page) .. '"')
	end
	if not isBlank(stableKey) then
		table.insert(attributes, 'data-erenshor-key="' .. Format.escape(stableKey) .. '"')
	end
	if kind == "item" and not isBlank(quality) then
		table.insert(attributes, 'data-erenshor-quality="' .. Format.escape(quality) .. '"')
	end
	return table.concat(attributes, " ")
end

local function wrap(kind, args, body, page, quality, stableKey)
	if isBlank(body) then
		return ""
	end
	return "<span "
		.. spanAttributes(kind, args or {}, page, quality, stableKey)
		.. ">"
		.. body
		.. "</span>"
end

local function resolveItemQuality(args)
	local requested = Args.resolve(args or {}, "quality", nil, { dashBlank = false })
	if requested == nil then
		return nil
	end
	local canonical = Quality.canonicalName(requested)
	if canonical == nil then
		error(string.format("Parameter 'quality' has invalid value %q", tostring(requested)), 3)
	end
	return canonical
end

-- Resolve identity and presentation in one place. The catalog is the only
-- navigation source; item shards remain deliberately limited to itemRecord().
function p.resolve(kind, args)
	args = args or {}
	kind = tostring(kind or ""):lower()
	local requestedKey = explicitStableKey(args)
	local positionalPage = targetFor(kind, args)
	local namedPage = explicitPageFor(args)
	local suppliedPage = namedPage or positionalPage
	local textOverride = Args.resolve(args, "text", nil)
	local imageOverride = Args.resolve(args, "image", nil)
	local record = nil
	local state = "manual"
	local resolvedKey = nil

	if requestedKey ~= nil then
		record = resolveRecord(kind, requestedKey)
		if record ~= nil then
			state = "resolved"
			resolvedKey = requestedKey
		else
			state = "unresolved"
			warnUnresolved(kind, requestedKey)
		end
	elseif not isBlank(suppliedPage) then
		local matches = pageMatches(kind, suppliedPage)
		if #matches == 1 then
			state = "resolved"
			record = matches[1]
			resolvedKey = record.key
		elseif #matches > 1 then
			state = "ambiguous"
		end
	end

	local page
	if suppliedPage ~= nil then
		page = suppliedPage
	elseif record ~= nil then
		page = record.page
	end
	local text = textOverride
	if text == nil then
		if requestedKey == nil and not isBlank(positionalPage) then
			text = positionalPage
		elseif record ~= nil then
			text = record.name
		else
			text = positionalPage or suppliedPage or page
		end
	end
	local image = imageOverride or (record and record.image)

	if requestedKey ~= nil and record ~= nil and namedPage ~= nil then
		local expected = normalizePage(record.page)
		local actual = normalizePage(suppliedPage)
		if actual ~= expected then
			warnMismatch(kind, requestedKey, suppliedPage, record.page)
			state = "resolved"
		end
	end

	return {
		state = state,
		requestedKey = requestedKey,
		resolvedKey = resolvedKey,
		record = record,
		page = page,
		text = text,
		image = image,
	}
end

local function unresolvedBody(kind, requestedKey)
	return '<span class="erenshor-link erenshor-link--unresolved">Unresolved '
		.. Format.escape(kind)
		.. " link: "
		.. Format.escape(requestedKey)
		.. "</span>"
end

local function renderResolved(kind, args, result)
	local page = result.page
	local text = result.text
	if result.state == "unresolved" and isBlank(page) then
		return unresolvedBody(kind, result.requestedKey)
	end

	if kind == "item" then
		local quality = resolveItemQuality(args)
		local image = result.image or page or text
		local imageLink = Format.fileLink(
			ensureImageFile(image, page or text),
			{ alt = text, size = "24x24px", link = page }
		)
		local body
		if Args.bool(args, "imageonly", false) then
			body = imageLink
		else
			body = imageLink .. " " .. Format.pageLink(page, text)
		end
		return wrap(kind, args, body, page, quality, result.resolvedKey or result.requestedKey)
	elseif kind == "ability" then
		local image = result.image or text
		local imageLink =
			Format.fileLink(ensureImageFile(image, text), { size = "24x24px", link = page })
		local body = '<span style="color:#fff;text-shadow:1px 1px 10px red, 1px 1px 10px orange;">'
			.. imageLink
		if Args.resolve(args, "imageonly", nil) ~= "1" then
			body = body .. " " .. Format.pageLink(page, text)
		end
		body = body .. "</span>"
		return wrap(kind, args, body, page, nil, result.resolvedKey or result.requestedKey)
	end
	return wrap(
		kind,
		args,
		Format.pageLink(page, text),
		page,
		nil,
		result.resolvedKey or result.requestedKey
	)
end

function p.render(args)
	args = args or {}
	local kind = Args.resolve(args, "kind", nil)
	if isBlank(kind) then
		return ""
	end
	kind = tostring(kind):lower()
	local result = p.resolve(kind, args)
	local output = renderResolved(kind, args, result)
	if result.state == "unresolved" then
		output = appendCategory(output, UNRESOLVED_CATEGORY)
	elseif result.state == "ambiguous" then
		output = appendCategory(output, AMBIGUOUS_CATEGORY)
	end
	-- A mismatched valid key remains resolved for navigation but is tracked.
	if result.state == "resolved" and result.requestedKey ~= nil and result.record ~= nil then
		local suppliedPage = explicitPageFor(args)
		if
			suppliedPage ~= nil
			and normalizePage(suppliedPage) ~= normalizePage(result.record.page)
		then
			output = appendCategory(output, MISMATCH_CATEGORY)
		end
	end
	return output
end

function p.join(values, separator)
	if values == nil then
		return ""
	end
	local out = {}
	for _, value in ipairs(values) do
		local rendered = p.render(value)
		if not isBlank(rendered) then
			table.insert(out, rendered)
		end
	end
	return table.concat(out, separator or "<br>")
end

-- Resolve an item record (page, name, image, unique, …) by StableKey. Lets other
-- modules read item-owned facts at the display layer instead of denormalizing them
-- into every relationship that references the item.
function p.itemRecord(stableKey)
	return itemByStableKey(stableKey)
end

local function renderFrame(frame, kind)
	local args = templateArgs(frame)
	args.kind = kind
	return p.render(args)
end

function p.item(frame)
	return renderFrame(frame, "item")
end

function p.ability(frame)
	return renderFrame(frame, "ability")
end

function p.quest(frame)
	return renderFrame(frame, "quest")
end

function p.character(frame)
	return renderFrame(frame, "character")
end

function p.zone(frame)
	return renderFrame(frame, "zone")
end

function p.faction(frame)
	return renderFrame(frame, "faction")
end

function p.class(frame)
	return renderFrame(frame, "class")
end

return p

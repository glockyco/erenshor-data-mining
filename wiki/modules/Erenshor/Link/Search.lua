local p = {}

local VALID_KINDS = {
	item = true,
	ability = true,
	character = true,
	quest = true,
	zone = true,
	faction = true,
	class = true,
}

local function trim(value)
	local trimmed = tostring(value or "")
	trimmed = mw.ustring.gsub(trimmed, "^%s+", "")
	trimmed = mw.ustring.gsub(trimmed, "%s+$", "")
	return trimmed
end

local function normalize(value)
	if value == nil then
		return ""
	end
	return mw.ustring.lower(trim(mw.uri.decode(tostring(value))))
end

local function field(record, name)
	return tostring(record[name] or "")
end

local function startsWith(value, prefix)
	return mw.ustring.sub(value, 1, mw.ustring.len(prefix)) == prefix
end

local function contains(value, needle)
	return mw.ustring.find(value, needle, 1, true) ~= nil
end

local function rank(record, query)
	local key = normalize(record.key)
	local name = normalize(record.name)
	local page = normalize(record.page)

	if query == key then
		return 1
	end
	if query == name then
		return 2
	end
	if query == page then
		return 3
	end
	if startsWith(name, query) then
		return 4
	end
	if startsWith(page, query) then
		return 5
	end
	if startsWith(key, query) then
		return 6
	end
	if contains(name, query) or contains(page, query) or contains(key, query) then
		return 7
	end
	return nil
end

local function resultFor(record)
	return {
		key = field(record, "key"),
		kind = field(record, "kind"),
		subtype = field(record, "subtype"),
		name = field(record, "name"),
		page = field(record, "page"),
		image = field(record, "image"),
	}
end

local function lessString(left, right)
	if left == right then
		return false
	end
	return left < right
end

local function lessCandidate(left, right)
	if left.rank ~= right.rank then
		return left.rank < right.rank
	end
	if left.record.name ~= right.record.name then
		return lessString(field(left.record, "name"), field(right.record, "name"))
	end
	if left.record.kind ~= right.record.kind then
		return lessString(field(left.record, "kind"), field(right.record, "kind"))
	end
	if left.record.subtype ~= right.record.subtype then
		return lessString(field(left.record, "subtype"), field(right.record, "subtype"))
	end
	return lessString(field(left.record, "key"), field(right.record, "key"))
end

function p.query(frame)
	local args = frame and frame.args or {}
	local query = normalize(args.q)
	local kind = normalize(args.kind)
	local results = {}

	if mw.ustring.len(query) >= 2 and (kind == "" or VALID_KINDS[kind]) then
		local catalog = mw.loadData("Module:Erenshor/Data/Links")
		for _, record in ipairs(catalog.entries or {}) do
			if kind == "" or normalize(record.kind) == kind then
				local recordRank = rank(record, query)
				if recordRank ~= nil then
					table.insert(results, { rank = recordRank, record = record })
				end
			end
		end
		table.sort(results, lessCandidate)
	end

	local output = {}
	for index = 1, math.min(#results, 25) do
		output[index] = resultFor(results[index].record)
	end

	return mw.text.jsonEncode({
		schemaVersion = 1,
		query = query,
		results = output,
	})
end

return p

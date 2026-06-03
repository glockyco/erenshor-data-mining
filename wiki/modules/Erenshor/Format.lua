local p = {}

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

local function appendNonBlank(parts, value)
	if not isBlank(value) then
		table.insert(parts, tostring(value))
	end
end

function p.escape(value)
	if value == nil then
		return ""
	end

	local text = tostring(value)
	text = text:gsub("&", "&amp;")
	text = text:gsub("<", "&lt;")
	text = text:gsub(">", "&gt;")
	return text
end

function p.pageLink(page, label)
	if isBlank(page) then
		return ""
	end

	if isBlank(label) or tostring(label) == tostring(page) then
		return string.format("[[%s]]", tostring(page))
	end

	return string.format("[[%s|%s]]", tostring(page), tostring(label))
end

function p.fileLink(file, options)
	if isBlank(file) then
		return ""
	end

	options = options or {}
	local parts = { string.format("[[File:%s", tostring(file)) }
	appendNonBlank(parts, options.size)
	if not isBlank(options.alt) then
		table.insert(parts, "alt=" .. tostring(options.alt))
	end
	appendNonBlank(parts, options.caption)

	return table.concat(parts, "|") .. "]]"
end

function p.classList(classes)
	if classes == nil then
		return ""
	end

	local links = {}
	for _, class in ipairs(classes) do
		if not isBlank(class) then
			table.insert(links, p.pageLink(class))
		end
	end

	return table.concat(links, " / ")
end

function p.currency(value)
	local amount = tonumber(value)
	if amount == nil then
		return ""
	end

	amount = math.floor(amount)
	local gold = math.floor(amount / 10000)
	amount = amount % 10000
	local silver = math.floor(amount / 100)
	local copper = amount % 100

	local parts = {}
	if gold > 0 then
		table.insert(parts, tostring(gold) .. "g")
	end
	if silver > 0 then
		table.insert(parts, tostring(silver) .. "s")
	end
	if copper > 0 or #parts == 0 then
		table.insert(parts, tostring(copper) .. "c")
	end

	return table.concat(parts, " ")
end

function p.signedStat(value)
	local amount = tonumber(value) or 0
	if amount >= 0 then
		return "+" .. tostring(amount)
	end
	return tostring(amount)
end

function p.resistLabel(resist)
	if isBlank(resist) then
		return ""
	end

	local text = tostring(resist):lower()
	return text:sub(1, 1):upper() .. text:sub(2) .. " Resist"
end

function p.categories(categories)
	if categories == nil then
		return ""
	end

	local out = {}
	for _, category in ipairs(categories) do
		if not isBlank(category) then
			table.insert(out, string.format("[[Category:%s]]", tostring(category)))
		end
	end

	return table.concat(out)
end

return p

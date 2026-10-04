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
	if not isBlank(options.link) then
		table.insert(parts, "link=" .. tostring(options.link))
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

-- Erenshor uses a single gold currency (Item.ItemValue is a flat integer the
-- game prints verbatim); there is no silver/copper. Render the raw value.
function p.currency(value)
	local amount = tonumber(value)
	if amount == nil then
		return ""
	end
	return tostring(math.floor(amount))
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

-- A duration in seconds as the infobox shows it: "1 second", "9 seconds",
-- "13.33 seconds". A whole number has no decimal places.
function p.seconds(value)
	local number = tonumber(value)
	if number == nil then
		return ""
	end
	local text = number == math.floor(number) and tostring(math.floor(number)) or tostring(number)
	return text .. (number == 1 and " second" or " seconds")
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

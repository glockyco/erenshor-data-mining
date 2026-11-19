local p = {}

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
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

-- MediaWiki collapses raw attribute whitespace. Encode serialized identity attributes, not raw values.
-- additionalAttributes is an optional set of exact attribute names whose values also carry identities.
function p.preserveIdentityAttributes(html, additionalAttributes)
	local output = tostring(html):gsub('(data%-erenshor%-[%w%-]+)="([^"]*)"', function(name, key)
		if not name:match("key$") and not (additionalAttributes and additionalAttributes[name]) then
			return name .. '="' .. key .. '"'
		end
		local encoded = key:gsub("%s+", function(spaces)
			if spaces == " " then
				return spaces
			end
			return spaces:gsub(".", function(character)
				return "&#" .. string.byte(character) .. ";"
			end)
		end)
		return name .. '="' .. encoded .. '"'
	end)
	return output
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

local function classValues(value)
	if type(value) == "table" then
		value = value.args[1]
	end
	local values = {}
	for entry in tostring(value or ""):gmatch("[^,]+") do
		local trimmed = mw.text.trim(entry)
		if trimmed ~= "" then
			values[#values + 1] = trimmed
		end
	end
	return values
end

function p.classSpans(value)
	local spans = {}
	for _, name in ipairs(classValues(value)) do
		spans[#spans + 1] = '<span class="item-tooltip-class">' .. p.escape(name) .. "</span>"
	end
	return table.concat(spans)
end

function p.classLevelRows(value)
	local rows = {}
	for _, pair in ipairs(classValues(value)) do
		local name, level = pair:match("^(.-)%s*:%s*(%d+)$")
		name = name and mw.text.trim(name)
		local requiredLevel = tonumber(level)
		if isBlank(name) or requiredLevel == nil or requiredLevel <= 0 then
			error("Invalid class level pair: " .. pair, 2)
		end
		rows[#rows + 1] = '<div class="item-tooltip-book-class-req">'
			.. p.escape(name)
			.. ": "
			.. tostring(requiredLevel)
			.. "</div>"
	end
	return table.concat(rows)
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

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

local function classLevels(value)
	local levels = {}
	for _, pair in ipairs(classValues(value)) do
		local name, level = pair:match("^(.-)%s*:%s*(%d+)$")
		name = name and mw.text.trim(name)
		local requiredLevel = tonumber(level)
		if isBlank(name) or requiredLevel == nil or requiredLevel <= 0 then
			error("Invalid class level pair: " .. pair, 2)
		end
		levels[#levels + 1] = { name = name, level = requiredLevel }
	end
	return levels
end

local function levelRows(levels)
	local rows = {}
	for _, entry in ipairs(levels) do
		rows[#rows + 1] = '<div class="item-tooltip-book-class-req">'
			.. p.escape(entry.name)
			.. ": "
			.. tostring(entry.level)
			.. "</div>"
	end
	return table.concat(rows)
end

function p.classLevelRows(value)
	return levelRows(classLevels(value))
end

function p.classBand(frame)
	local names = frame.args[1]
	if isBlank(names) then
		local fromLevels = {}
		for _, entry in ipairs(classLevels(frame.args[2])) do
			fromLevels[#fromLevels + 1] = entry.name
		end
		names = table.concat(fromLevels, ", ")
	end
	local spans = p.classSpans(names)
	if spans == "" then
		return ""
	end
	return '<div class="item-tooltip-classes">' .. spans .. "</div>"
end

function p.bookLevels(frame)
	local levels = classLevels(frame.args[1])
	if #levels == 0 then
		return ""
	end
	local shared = frame.args[2] == "scroll"
	local first = levels[1].level
	for _, entry in ipairs(levels) do
		shared = shared and entry.level == first
	end
	local label = '<div class="item-tooltip-book-requirement">Required Level:'
	if shared then
		return label .. " " .. first .. "</div>"
	end
	return label
		.. '</div><div class="item-tooltip-book-class-requirements">'
		.. levelRows(levels)
		.. "</div>"
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

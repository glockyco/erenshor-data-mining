local Format = require("Module:Erenshor/Format")

local p = {}

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

local function classAttribute(classes, defaults)
	local out = {}
	for _, class in ipairs(defaults or {}) do
		if not isBlank(class) then
			table.insert(out, tostring(class))
		end
	end
	for _, class in ipairs(classes or {}) do
		if not isBlank(class) then
			table.insert(out, tostring(class))
		end
	end
	return table.concat(out, " ")
end

local function appendCell(buffer, tag, value)
	table.insert(buffer, "<")
	table.insert(buffer, tag)
	table.insert(buffer, ">")
	table.insert(buffer, tostring(value))
	table.insert(buffer, "</")
	table.insert(buffer, tag)
	table.insert(buffer, ">")
end

function p.infobox(spec)
	spec = spec or {}
	local buffer = {}
	local classes = classAttribute(spec.classes, { "infobox", "erenshor-infobox" })

	table.insert(buffer, '<table class="')
	table.insert(buffer, Format.escape(classes))
	table.insert(buffer, '">')

	if not isBlank(spec.title) then
		table.insert(buffer, "<caption>")
		table.insert(buffer, Format.escape(spec.title))
		table.insert(buffer, "</caption>")
	end

	for _, row in ipairs(spec.rows or {}) do
		if row ~= nil and not isBlank(row.value) then
			table.insert(buffer, "<tr>")
			appendCell(buffer, "th", Format.escape(row.label or ""))
			appendCell(buffer, "td", row.value)
			table.insert(buffer, "</tr>")
		end
	end

	table.insert(buffer, "</table>")
	return table.concat(buffer)
end

function p.table(spec)
	spec = spec or {}
	local buffer = {}
	local classes = classAttribute(spec.classes, {})

	table.insert(buffer, '<table class="')
	table.insert(buffer, Format.escape(classes))
	table.insert(buffer, '">')

	if spec.headers ~= nil then
		table.insert(buffer, "<tr>")
		for _, header in ipairs(spec.headers) do
			appendCell(buffer, "th", Format.escape(header))
		end
		table.insert(buffer, "</tr>")
	end

	for _, row in ipairs(spec.rows or {}) do
		table.insert(buffer, "<tr>")
		for _, value in ipairs(row) do
			appendCell(buffer, "td", value)
		end
		table.insert(buffer, "</tr>")
	end

	table.insert(buffer, "</table>")
	return table.concat(buffer)
end

return p

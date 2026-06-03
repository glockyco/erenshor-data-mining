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

local function typeClass(spec, classes)
	if not isBlank(spec.type) then
		return tostring(spec.type)
	end
	for _, class in ipairs(classes or {}) do
		if not isBlank(class) then
			return tostring(class):gsub("^erenshor%-", ""):gsub("%-infobox$", "")
		end
	end
	return "default"
end

local function dataSource(label)
	return tostring(label or ""):gsub("[^%w]+", "")
end

local function labelText(label)
	local text = tostring(label or "")
	if text == "Map" or text:sub(-1) == ":" then
		return text
	end
	return text .. ":"
end

local function appendDataRow(buffer, row)
	if row == nil or isBlank(row.value) then
		return
	end
	table.insert(
		buffer,
		'<div class="pi-item pi-data pi-item-spacing pi-border-color" data-source="'
	)
	table.insert(buffer, Format.escape(dataSource(row.label)))
	table.insert(buffer, '"><div class="pi-data-label pi-secondary-font">')
	table.insert(buffer, Format.escape(labelText(row.label)))
	table.insert(buffer, '</div><div class="pi-data-value pi-font">')
	table.insert(buffer, tostring(row.value))
	table.insert(buffer, "</div></div>")
end

local function appendImage(buffer, row)
	if row == nil or isBlank(row.value) then
		return false
	end
	table.insert(buffer, '<div class="pi-item pi-media pi-image" data-source="image">')
	table.insert(buffer, tostring(row.value))
	table.insert(buffer, "</div>")
	return true
end

local function nonEmptyRows(rows)
	local out = {}
	for _, row in ipairs(rows or {}) do
		if row ~= nil and not isBlank(row.value) then
			table.insert(out, row)
		end
	end
	return out
end

local function appendHorizontalGroup(buffer, group)
	local rows = nonEmptyRows(group.rows)
	if #rows == 0 then
		return
	end
	table.insert(
		buffer,
		'<div class="pi-item pi-group pi-border-color"><table class="pi-horizontal-group"><tr>'
	)
	for _, row in ipairs(rows) do
		table.insert(
			buffer,
			'<th class="pi-horizontal-group-item pi-data-label pi-secondary-font pi-border-color pi-item-spacing" data-source="'
		)
		table.insert(buffer, Format.escape(dataSource(row.label)))
		table.insert(buffer, '">')
		table.insert(buffer, Format.escape(labelText(row.label)))
		table.insert(buffer, "</th>")
	end
	table.insert(buffer, "</tr><tr>")
	for _, row in ipairs(rows) do
		table.insert(
			buffer,
			'<td class="pi-horizontal-group-item pi-data-value pi-font pi-border-color pi-item-spacing" data-source="'
		)
		table.insert(buffer, Format.escape(dataSource(row.label)))
		table.insert(buffer, '">')
		table.insert(buffer, tostring(row.value))
		table.insert(buffer, "</td>")
	end
	table.insert(buffer, "</tr></table></div>")
end

local function appendSectionContent(buffer, entry)
	if entry.kind == "horizontal" then
		appendHorizontalGroup(buffer, entry)
	else
		appendDataRow(buffer, entry)
	end
end

local function appendSection(buffer, section)
	if section == nil or isBlank(section.title) then
		return
	end
	table.insert(
		buffer,
		'<div class="pi-item pi-header pi-secondary-font pi-item-spacing pi-secondary-background">'
	)
	table.insert(buffer, Format.escape(section.title))
	table.insert(buffer, "</div>")
	for _, row in ipairs(section.rows or {}) do
		appendSectionContent(buffer, row)
	end
	for _, group in ipairs(section.groups or {}) do
		appendSectionContent(buffer, group)
	end
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
	local customClasses = classAttribute(spec.classes, {})
	local classes = classAttribute({
		customClasses,
		"pi-type-" .. typeClass(spec, spec.classes),
	}, {
		"portable-infobox",
		"noexcerpt",
		"searchaux",
		"pi-background",
		"pi-theme-default",
		"pi-layout-default",
	})

	table.insert(buffer, '<div class="')
	table.insert(buffer, Format.escape(classes))
	table.insert(buffer, '">')

	if not isBlank(spec.title) then
		table.insert(buffer, '<div class="pi-item pi-item-spacing pi-title" data-source="name">')
		table.insert(buffer, Format.escape(spec.title))
		table.insert(buffer, "</div>")
	end

	for _, row in ipairs(spec.rows or {}) do
		if row ~= nil and row.label == "Image" then
			appendImage(buffer, row)
		else
			appendDataRow(buffer, row)
		end
	end

	for _, section in ipairs(spec.sections or {}) do
		appendSection(buffer, section)
	end

	table.insert(buffer, "</div>")
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

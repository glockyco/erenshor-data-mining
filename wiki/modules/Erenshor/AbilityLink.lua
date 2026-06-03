local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")

local Data = mw.loadData("Module:Erenshor/Data/AbilityLinks")

local p = {}

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
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

local function copyTable(value)
	local out = {}
	if value == nil then
		return out
	end
	for key, item in pairs(value) do
		if type(item) == "table" then
			out[key] = copyTable(item)
		else
			out[key] = item
		end
	end
	return out
end

local function templateArgs(frame)
	local out = copyTable(Args.parentArgs(frame))
	if frame ~= nil and frame.args ~= nil then
		for key, value in pairs(frame.args) do
			out[key] = value
		end
	end
	return out
end

local function stableKeyForTarget(target)
	if isBlank(target) then
		return nil
	end
	return Data.byName[tostring(target)]
end

function p.resolve(args)
	args = args or {}
	local target = Args.resolve(args, 1, nil)
	local stableKey = Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "key", nil)
		or stableKeyForTarget(target)
	local ability = nil
	if stableKey ~= nil then
		ability = copyTable(Data.abilities[stableKey])
	end
	if ability == nil then
		ability = {
			name = target,
			page = target,
			image = target,
		}
	end

	ability.page = Args.resolve(args, "link", ability.page)
	ability.name = Args.resolve(args, "text", ability.name)
	ability.image = Args.resolve(args, "image", ability.image)
	return ability
end

local function linkedImage(ability)
	local image = ensureImageFile(ability.image, ability.name)
	if isBlank(image) then
		return ""
	end
	local page = ability.page
	if isBlank(page) then
		return Format.fileLink(image, { size = "30px", alt = ability.name })
	end
	return string.format("[[File:%s|30px|link=%s]]", tostring(image), tostring(page))
end

function p.render(args)
	local ability = p.resolve(args)
	local parts = {
		'<span style="color:#fff;text-shadow:1px 1px 10px red, 1px 1px 10px orange;">',
		linkedImage(ability),
	}
	if Args.resolve(args or {}, "imageonly", nil) ~= "1" then
		table.insert(parts, " ")
		table.insert(parts, Format.pageLink(ability.page, ability.name))
	end
	table.insert(parts, "</span>")
	return table.concat(parts)
end

function p.link(frame)
	return p.render(templateArgs(frame))
end

return p

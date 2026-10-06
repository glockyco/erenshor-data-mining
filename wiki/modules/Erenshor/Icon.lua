-- Module:Erenshor/Icon
-- Draw game frames around native textures without changing the artwork's proportions.
-- render(frame, { file, kind = "item" or "ability", size, link, alt }) returns wikitext.
-- An empty link disables navigation; an omitted link opens the file page.
local Args = require("Module:Erenshor/Args")

local Icon = {}

function Icon.render(frame, args)
	args = args or {}
	local file = Args.trim(args.file)
	if Args.isBlank(file) then
		error("Icon argument 'file' is required", 2)
	end
	local kind = Args.trim(args.kind)
	if kind ~= "item" and kind ~= "ability" then
		error("Icon argument 'kind' must be item or ability", 2)
	end
	local size = tonumber(args.size)
	if size == nil or size <= 0 or size == math.huge or size ~= math.floor(size) then
		error("Icon argument 'size' must be a positive integer", 2)
	end
	local pixels = string.format("%d", size)
	local options = pixels .. "x" .. pixels .. "px"
	if args.alt ~= nil then
		options = options .. "|alt=" .. tostring(args.alt)
	end
	if args.link ~= nil then
		options = options .. "|link=" .. tostring(args.link)
	end
	local root = mw.html
		.create("span")
		:addClass("erenshor-icon")
		:addClass("erenshor-icon--" .. kind)
		:css("width", pixels .. "px")
		:css("height", pixels .. "px")
	if kind == "item" then
		local inset = math.max(1, math.floor(size * 9 / 256 + 0.5)) .. "px"
		root:tag("span")
			:addClass("erenshor-icon-well")
			:css("top", inset)
			:css("right", inset)
			:css("bottom", inset)
			:css("left", inset)
	end
	root:tag("span")
		:addClass("erenshor-icon-art")
		:wikitext("[[File:" .. file .. "|" .. options .. "]]")
	if kind == "ability" then
		root:tag("span")
			:addClass("erenshor-icon-frame")
			:attr("aria-hidden", "true")
			:wikitext("[[File:Hotbar Frame.png|" .. pixels .. "x" .. pixels .. "px|link=|alt=]]")
	end
	return frame:extensionTag("templatestyles", "", { src = "Template:Icon/styles.css" })
		.. tostring(root)
end

function Icon.main(frame)
	local args = Args.parentArgs(frame)
	return Icon.render(frame, {
		file = args[1],
		kind = args.kind,
		size = args.size,
		link = args.link,
		alt = args.alt,
	})
end

return Icon

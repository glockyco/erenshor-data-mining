local Icon = require("Module:Erenshor/Icon")

local p = {}

local function assertContains(actual, expected, label)
	if string.find(actual, expected, 1, true) == nil then
		error(label .. ": expected output to contain " .. expected, 2)
	end
end

local function assertNotContains(actual, unexpected, label)
	if string.find(actual, unexpected, 1, true) ~= nil then
		error(label .. ": unexpected " .. unexpected, 2)
	end
end

function p.run(frame)
	local stylesheetCalls = 0
	local fakeFrame = {
		extensionTag = function(_, name, content, attributes)
			if
				name ~= "templatestyles"
				or content ~= ""
				or attributes.src ~= "Template:Icon/styles.css"
			then
				error("Icon must load its TemplateStyles stylesheet", 2)
			end
			stylesheetCalls = stylesheetCalls + 1
			return "ICON_STYLES"
		end,
	}
	for _, size in ipairs({ 80, 48, 24 }) do
		for _, kind in ipairs({ "item", "ability", "window", "bare" }) do
			local markup = Icon.render(fakeFrame, {
				file = "Thorned Branch.png",
				kind = kind,
				size = size,
				link = "Thorned Branch",
				alt = "Branch",
			})
			assertContains(markup, "ICON_STYLES", "stylesheet included")
			assertContains(
				markup,
				'class="erenshor-icon erenshor-icon--' .. kind .. '"',
				"slot kind"
			)
			assertContains(markup, "width:" .. size .. "px", "slot width")
			assertContains(markup, "height:" .. size .. "px", "slot height")
			assertContains(
				markup,
				"[[File:Thorned Branch.png|"
					.. size
					.. "x"
					.. size
					.. "px|alt=Branch|link=Thorned Branch]]",
				"fitted linked artwork"
			)
			if kind == "item" then
				local inset = size == 80 and 3 or size == 48 and 2 or 1
				assertContains(markup, 'class="erenshor-icon-well"', "item dark well")
				for _, side in ipairs({ "top", "right", "bottom", "left" }) do
					assertContains(markup, side .. ":" .. inset .. "px", "rounded ring inset")
				end
				assertNotContains(markup, "Hotbar Frame.png", "items have no hotbar bezel")
			elseif kind == "bare" then
				assertNotContains(markup, "Hotbar Frame.png", "a bare icon has no frame")
				assertNotContains(markup, "erenshor-icon-well", "a bare icon has no well")
			else
				assertContains(markup, 'class="erenshor-icon-frame"', "hotbar frame layer")
				assertContains(
					markup,
					"[[File:Hotbar Frame.png|" .. size .. "x" .. size .. "px|link=|alt=]]",
					"nonlinked hotbar frame"
				)
				assertNotContains(markup, "erenshor-icon-well", "hotbar frames have no item well")
				local art = string.find(markup, "erenshor-icon-art", 1, true)
				local overlay = string.find(markup, "erenshor-icon-frame", 1, true)
				-- Later layers draw above earlier ones: the hotbar draws its frame over
				-- the art, and the item window draws the art over its frame.
				if kind == "ability" and art >= overlay then
					error("Hotbar frame must follow art so it draws above it", 2)
				elseif kind == "window" and overlay >= art then
					error("Item window art must follow its frame so it draws above it", 2)
				end
			end
		end
	end
	if stylesheetCalls ~= 12 then
		error("Every icon render must include TemplateStyles", 2)
	end
	local unlinked =
		Icon.render(fakeFrame, { file = "Branch.png", kind = "item", size = 24, link = "" })
	assertContains(unlinked, "[[File:Branch.png|24x24px|link=]]", "empty link disables navigation")
	local templateFrame = {
		getParent = function()
			return { args = { [1] = "Branch.png", kind = "item", size = "24", link = "" } }
		end,
		extensionTag = fakeFrame.extensionTag,
	}
	assertContains(
		Icon.main(templateFrame),
		"[[File:Branch.png|24x24px|link=]]",
		"template parent arguments"
	)
	for _, case in ipairs({
		{ args = { kind = "item", size = 24 }, argument = "file" },
		{ args = { file = " ", kind = "item", size = 24 }, argument = "file" },
		{ args = { file = "Branch.png", size = 24 }, argument = "kind" },
		{ args = { file = "Branch.png", kind = "spell", size = 24 }, argument = "kind" },
		{ args = { file = "Branch.png", kind = "item" }, argument = "size" },
	}) do
		local ok, err = pcall(Icon.render, frame, case.args)
		if ok then
			error("Invalid icon must fail", 2)
		end
		assertContains(tostring(err), "'" .. case.argument .. "'", "error names argument")
	end
	for _, size in ipairs({ 0, -1, 1.5, "80px", "abc", math.huge, 0 / 0 }) do
		local ok, err =
			pcall(Icon.render, frame, { file = "Branch.png", kind = "item", size = size })
		if ok then
			error("Invalid size must fail", 2)
		end
		assertContains(tostring(err), "'size'", "size error names argument")
	end
	return "PASS Erenshor Icon testcases"
end

return p

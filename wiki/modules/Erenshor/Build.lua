local build = mw.loadData("Module:Erenshor/Data/Build")

local p = {}

function p.id(frame)
	return build.gameBuildId
end

function p.published(frame)
	return string.sub(build.publishedAt, 1, 10)
end

function p.text(frame)
	return "build " .. p.id(frame) .. " (published " .. p.published(frame) .. ")"
end

return p

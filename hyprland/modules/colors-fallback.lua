--     ____     ______            __
--    / __/__ _/ / / /  ___ _____/ /__
--   / _// _ `/ / / _ \/ _ `/ __/  '_/
--  /_/  \_,_/_/_/_.__/\_,_/\__/_/\_\

-- Static fallback palette used before matugen generates modules/colors.lua.
-- Not wallpaper-derived: these values never change with the wallpaper.
-- by ae. Orlando
-- _______________________________________________________________________

local colors = {
    -- gradient table for the active border (must provide a "colors" array)
    active_border   = { colors = { "rgba(8ad6b7ee)", "rgba(b3ccbfee)" }, angle = 45 },
    inactive_border = "rgba(89938daa)",
    shadow          = 0xee000000,
}

return colors

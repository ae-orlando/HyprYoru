--    _____                      __
--   / ___/__ ___  ___ _______ _/ /
--  / (_ / -_) _ \/ -_) __/ _ `/ /
--  \___/\__/_//_/\__/_/  \_,_/_/

-- Look and feel, animations, misc.
-- by ae. Orlando
-- _______________________________________________________________________

-- https://wiki.hypr.land/Configuring/Basics/Variables/

local ok, mod = pcall(require, "modules.colors")
-- Live matugen palette when present; otherwise the tracked static fallback.
-- The generated modules/colors.lua is a gitignored artifact (see .gitignore).
local colors = ok and mod or require("modules.colors-fallback")

hl.config({
    general = {
        gaps_in = 5,
        gaps_out = 10,

        border_size = 2,

        col = {
            active_border = colors.active_border,
            inactive_border = colors.inactive_border,
        },

        -- Resize by dragging borders and gaps.
        resize_on_border = true,
        extend_border_grab_area = 15,

        -- Read https://wiki.hypr.land/Configuring/Advanced-and-Cool/Tearing/ first.
        allow_tearing = false,

        layout = "dwindle",
    },

    decoration = {
        rounding = 10,
        rounding_power = 3,

        shadow = {
            enabled = true,
            range = 4,
            render_power = 3,
            color = colors.shadow,
        },

        blur = {
            enabled = true,
            size = 9,
            passes = 3,
            xray = true,
            noise = 0.04,
            contrast = 1.5,
            new_optimizations = true,
        },
    },

    animations = {
        enabled = true,
    },
})

-- Bezier curves and springs (https://wiki.hypr.land/Configuring/Advanced-and-Cool/Animations/).
hl.curve("easeOutQuint", { type = "bezier", points = { { 0.23, 1 }, { 0.32, 1 } } })
hl.curve("easeInOutCubic", { type = "bezier", points = { { 0.65, 0.05 }, { 0.36, 1 } } })
hl.curve("linear", { type = "bezier", points = { { 0, 0 }, { 1, 1 } } })
hl.curve("almostLinear", { type = "bezier", points = { { 0.5, 0.5 }, { 0.75, 1 } } })
hl.curve("quick", { type = "bezier", points = { { 0.15, 0 }, { 0.1, 1 } } })

-- Springs
hl.curve("easy", { type = "spring", mass = 1, stiffness = 238.1191, dampening = 24.21279333 })

-- Default animations
hl.animation({ leaf = "global", enabled = true, speed = 10, bezier = "default" })
hl.animation({ leaf = "border", enabled = true, speed = 5.39, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows", enabled = true, speed = 4.79, spring = "easy" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 4.1, spring = "easy", style = "popin 87%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 1.49, bezier = "linear", style = "popin 87%" })
hl.animation({ leaf = "fadeIn", enabled = true, speed = 1.73, bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut", enabled = true, speed = 1.46, bezier = "almostLinear" })
hl.animation({ leaf = "fade", enabled = true, speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers", enabled = true, speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn", enabled = true, speed = 4, bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut", enabled = true, speed = 1.5, bezier = "linear", style = "fade" })
hl.animation({ leaf = "fadeLayersIn", enabled = true, speed = 1.79, bezier = "almostLinear" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 1.39, bezier = "almostLinear" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesIn", enabled = true, speed = 1.21, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesOut", enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "zoomFactor", enabled = true, speed = 7, bezier = "quick" })

-- Misc
hl.config({
    misc = {
        force_default_wallpaper = 0, -- Set to 0 or 1 to disable the anime mascot wallpapers
        disable_hyprland_logo = true, -- If true disables the random hyprland logo / anime girl background. :(
        -- Let notification-click activate requests focus the sender (e.g.
        -- Chromium) and switch workspace instead of just marking urgent.
        focus_on_activate = true,
    },
})

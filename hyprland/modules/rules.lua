-- Window and workspace rules.
-- by ae. Orlando
-- _______________________________________________________________________

-- https://wiki.hypr.land/Configuring/Basics/Window-Rules/

-- Opt-in "no gaps on single window" presets (uncomment to use).
-- hl.workspace_rule({ workspace = "w[tv1]", gaps_out = 0, gaps_in = 0 })
-- hl.workspace_rule({ workspace = "f[1]",   gaps_out = 0, gaps_in = 0 })
-- hl.window_rule({
--     name  = "no-gaps-wtv1",
--     match = { float = false, workspace = "w[tv1]" },
--     border_size = 0,
--     rounding    = 0,
-- })
-- hl.window_rule({
--     name  = "no-gaps-f1",
--     match = { float = false, workspace = "f[1]" },
--     border_size = 0,
--     rounding    = 0,
-- })

local suppressMaximizeRule = hl.window_rule({
	-- Ignore maximize requests from all apps.
	name = "suppress-maximize-events",
	match = { class = ".*" },

	suppress_event = "maximize",
})
-- suppressMaximizeRule:set_enabled(false)

hl.window_rule({
	-- Fix some dragging issues with XWayland
	name = "fix-xwayland-drags",
	match = {
		class = "^$",
		title = "^$",
		xwayland = true,
		float = true,
		fullscreen = false,
		pin = false,
	},

	no_focus = true,
})

-- Layer-rule example (disabled).
-- local overlayLayerRule = hl.layer_rule({
--     name  = "no-anim-overlay",
--     match = { namespace = "^my-overlay$" },
--     no_anim = true,
-- })
-- overlayLayerRule:set_enabled(false)

-- Blur behind translucent layer-shell surfaces (sWayNC glass, rofi).
hl.layer_rule({
	name = "blur-swaync",
	match = { namespace = "swaync-control-center|swaync-notification-window" },

	blur = true,
	ignore_alpha = 0.3,
})

hl.layer_rule({
	name = "blur-rofi",
	match = { namespace = "rofi" },

	blur = true,
	ignore_alpha = 0.3,
})

-- Hyprland-run popup placement.
hl.window_rule({
	name = "move-hyprland-run",
	match = { class = "hyprland-run" },

	move = "20 monitor_h-120",
	size = "600 80",
	float = true,
})

hl.window_rule({
	name = "waypaper-float",
	match = { class = "[Ww]aypaper" },

	float = true,
	size = "900 600",
	center = true,
})

-- Catch-all: center any other auto-floating windows so they
-- don't spawn anchored fullscreen/top-left.
hl.window_rule({
	name = "center-floating-catchall",
	match = { float = true },

	center = true,
})

hl.layer_rule({
	name = "notification-animations",
	match = { namespace = "swaync-control-center" },
	animation = "slide top",
})

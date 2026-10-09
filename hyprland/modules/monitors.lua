-- Monitors.
-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
hl.monitor({
	output = "eDP-1",
	mode = "1920x1080@60.02",
	position = "0x0",
	scale = "1",
})

-- Fallback for any other / hot-plugged monitor (see example hyprland.lua).
hl.monitor({
	output = "",
	mode = "preferred",
	position = "auto",
	scale = "auto",
})

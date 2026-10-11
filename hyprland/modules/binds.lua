-- Keybindings (descriptions double as the cheatsheet).
-- by ae. Orlando
-- _______________________________________________________________________

-- https://wiki.hypr.land/Configuring/Basics/Binds/

-- Programs
local terminal = "kitty"
local fileManager = "nautilus"
local browser = "chromium"
local music = "spotify"
local anime = browser .. " --app=https://www.miruro.tv"
local odel = browser .. " --app=https://e-learning.karu.ac.ke/my/"
local launcher = "~/.config/rofi/launchers/yoru-main.sh"
local runner = "~/.config/rofi/launchers/yoru-run.sh"
local codeCamp = browser .. " --app=https://www.freecodecamp.org/lear"
local whatsapp = browser .. " --app=https://web.whatsapp.com/"
local waybarReload = "~/.config/waybar/scripts/launch.sh"

local mainMod = "SUPER"
local shiftMod = "SUPER + SHIFT"

-- ==============================================
-- Apps
-- ==============================================
hl.bind(mainMod .. " + return", hl.dsp.exec_cmd(terminal), { description = "Open terminal" })
hl.bind(mainMod .. " + F", hl.dsp.exec_cmd(fileManager), { description = "Open file manager" })
hl.bind(mainMod .. " + B", hl.dsp.exec_cmd(browser), { description = "Open browser" })
hl.bind(mainMod .. " + M", hl.dsp.exec_cmd(music), { description = "Open music" })
hl.bind(mainMod .. " + O", hl.dsp.exec_cmd(odel), { description = "Open ODeL" })
hl.bind(mainMod .. " + A", hl.dsp.exec_cmd(anime), { description = "Open anime" })
hl.bind(mainMod .. " + Space", hl.dsp.exec_cmd(launcher), { description = "Open app launcher" })
hl.bind(shiftMod .. " + Space", hl.dsp.exec_cmd(runner), { description = "Run command" })
hl.bind(mainMod .. " + C", hl.dsp.exec_cmd(codeCamp), { description = "Open codeCamp" })
hl.bind(shiftMod .. " + C", hl.dsp.exec_cmd(whatsapp), { description = "Open Whatsapp" })

-- ===============================================
-- Hypr
-- ===============================================
hl.bind(mainMod .. " + R", hl.dsp.exec_cmd(waybarReload), { description = "Reload Waybar" })

hl.bind(mainMod .. " + Q", hl.dsp.window.close(), { description = "Close window" })

hl.bind(
	shiftMod .. " + Q",
	hl.dsp.exec_cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch exit"),
	{ description = "Quit Hyprland (hyprshutdown preferred)" }
)
hl.bind(mainMod .. " + T", hl.dsp.window.float({ action = "toggle" }), { description = "Toggle floating" })
hl.bind(
	shiftMod .. " + F",
	hl.dsp.window.fullscreen({ mode = "maximized" }),
	{ description = "Fullscreen (maximized)" }
)
hl.bind(mainMod .. " + P", hl.dsp.window.pseudo(), { description = "Toggle pseudotile" })
-- hl.bind(mainMod .. " + J", hl.dsp.layout("togglesplit"))    -- dwindle only

-- Move focus with mainMod + arrow keys
hl.bind(mainMod .. " + h", hl.dsp.focus({ direction = "left" }), { description = "Focus left" })
hl.bind(mainMod .. " + l", hl.dsp.focus({ direction = "right" }), { description = "Focus right" })
hl.bind(mainMod .. " + k", hl.dsp.focus({ direction = "up" }), { description = "Focus up" })
hl.bind(mainMod .. " + j", hl.dsp.focus({ direction = "down" }), { description = "Focus down" })

hl.bind(shiftMod .. " + h", hl.dsp.window.move({ direction = "left" }), { description = "Move window left" })
hl.bind(shiftMod .. " + l", hl.dsp.window.move({ direction = "right" }), { description = "Move window right" })
hl.bind(shiftMod .. " + k", hl.dsp.window.move({ direction = "up" }), { description = "Move window up" })
hl.bind(shiftMod .. " + j", hl.dsp.window.move({ direction = "down" }), { description = "Move window down" })

-- Resize active window with SUPER + arrows
hl.bind(
	mainMod .. " + left",
	hl.dsp.window.resize({ x = -50, y = 0, relative = true }),
	{ repeating = true, description = "Resize left" }
)
hl.bind(
	mainMod .. " + right",
	hl.dsp.window.resize({ x = 50, y = 0, relative = true }),
	{ repeating = true, description = "Resize right" }
)
hl.bind(
	mainMod .. " + up",
	hl.dsp.window.resize({ x = 0, y = -50, relative = true }),
	{ repeating = true, description = "Resize up" }
)
hl.bind(
	mainMod .. " + down",
	hl.dsp.window.resize({ x = 0, y = 50, relative = true }),
	{ repeating = true, description = "Resize down" }
)

-- Switch workspaces with mainMod + [0-9]
-- Move active window to a workspace with mainMod + SHIFT + [0-9]
for i = 1, 10 do
	local key = i % 10 -- 10 maps to key 0
	hl.bind(mainMod .. " + " .. key, hl.dsp.focus({ workspace = i }), { description = "Focus workspace " .. i })
	hl.bind(
		shiftMod .. " + " .. key,
		hl.dsp.window.move({ workspace = i }),
		{ description = "Move window to workspace " .. i }
	)
end

-- Special workspace (scratchpad): SUPER + grave (the ` / ~ key below Esc) toggles it,
-- SUPER + SHIFT + grave sends the focused window to it.
-- (SUPER + SHIFT + S is reserved for region screenshots, bound below.)
hl.bind(mainMod .. " + grave", hl.dsp.workspace.toggle_special("magic"), { description = "Toggle scratchpad" })
hl.bind(
	shiftMod .. " + grave",
	hl.dsp.window.move({ workspace = "special:magic" }),
	{ description = "Send window to scratchpad" }
)

-- Scroll through existing workspaces with mainMod + scroll
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), { description = "Next workspace" })
hl.bind(mainMod .. " + mouse_up", hl.dsp.focus({ workspace = "e-1" }), { description = "Previous workspace" })

-- Move/resize windows with mainMod + LMB/RMB and dragging
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(), { mouse = true, description = "Drag window" })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true, description = "Resize window" })

-- Laptop multimedia keys for volume and LCD brightness
hl.bind(
	"XF86AudioRaiseVolume",
	hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"),
	{ locked = true, repeating = true, description = "Volume up" }
)
hl.bind(
	"XF86AudioLowerVolume",
	hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),
	{ locked = true, repeating = true, description = "Volume down" }
)
hl.bind(
	"XF86AudioMute",
	hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),
	{ locked = true, repeating = true, description = "Mute toggle" }
)
hl.bind(
	"XF86AudioMicMute",
	hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),
	{ locked = true, repeating = true, description = "Mic mute toggle" }
)
hl.bind(
	"XF86MonBrightnessUp",
	hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"),
	{ locked = true, repeating = true, description = "Brightness up" }
)
hl.bind(
	"XF86MonBrightnessDown",
	hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"),
	{ locked = true, repeating = true, description = "Brightness down" }
)

-- Requires playerctl
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true, description = "Next track" })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true, description = "Play/pause" })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true, description = "Play/pause" })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true, description = "Previous track" })

-- Screenshots: region / fullscreen
hl.bind(
	mainMod .. " + SHIFT + S",
	hl.dsp.exec_cmd('grim -g "$(slurp)" - | wl-copy'),
	{ description = "Screenshot region to clipboard" }
)
hl.bind(mainMod .. " + PRINT", hl.dsp.exec_cmd("grim - | wl-copy"), { description = "Screenshot screen to clipboard" })

-- Lock the screen (SUPER+L conflicts with focus-right on lowercase l,
-- so bind to SUPER+U which is free; hyprlock now has a valid config)
hl.bind(mainMod .. " + U", hl.dsp.exec_cmd("hyprlock"), { description = "Lock screen" })

-- Night light: toggle hyprsunset blue-light filter (6500K <-> 4000K)
hl.bind(
	mainMod .. " + N",
	hl.dsp.exec_cmd("~/.config/hypr/scripts/nightlight.sh"),
	{ description = "Toggle night light" }
)
hl.bind(shiftMod .. " + N", hl.dsp.exec_cmd("swaync-client -t -sw"), { description = "Toggle notification center" })

-- Wallpaper picker (waypaper GUI, selector only) + system palette via post_command (matugen)
hl.bind(mainMod .. " + W", hl.dsp.exec_cmd("waypaper"), { description = "Pick wallpaper + regenerate palette" })
hl.bind(
	shiftMod .. " + W",
	hl.dsp.exec_cmd("waypaper --random"),
	{ description = "Random wallpaper + regenerate palette" }
)

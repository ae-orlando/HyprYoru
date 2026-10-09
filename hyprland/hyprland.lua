-- Hyprland entry point (Lua, see https://wiki.hypr.land/Configuring/Start/).
-- One topic per module; edit a module, then `hyprctl reload`.
--   colors    palette (matugen-generated, do not edit by hand)
--   env       environment variables          monitors  outputs
--   general   look, animations, misc         layouts   dwindle/master/scrolling
--   input     keyboard, touchpad, gestures   rules     windows, workspaces
--   binds     keybindings                    autostart compositor startup


-- See https://wiki.hypr.land/Configuring/Start/
require("modules.colors")
require("modules.env")
require("modules.monitors")
require("modules.general")
require("modules.layouts")
require("modules.input")
require("modules.rules")
require("modules.binds")
require("modules.autostart")
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
-- HYPRLAND CONFIG - ENTRY POINT                            --
--                                                          --
-- The configuration is split into topic modules (as the    --
-- wiki recommends). To change something, edit the module   --
-- and run `hyprctl reload` (or log out and back in).       --
--                                                          --
--   modules/colors.lua     -> color palette                        --
--   modules/env.lua        -> environment variables                --
--   modules/monitors.lua   -> monitor setup                        --
--   modules/general.lua    -> look & feel, animations, misc        --
--   modules/layouts.lua    -> dwindle / master / scrolling         --
--   modules/input.lua      -> keyboard, touchpad, gestures         --
--   modules/rules.lua      -> window & workspace rules             --
--   modules/binds.lua      -> keybindings                          --
--   modules/autostart.lua  -> apps started with the compositor     --
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --


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
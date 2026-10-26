--     ___       __           __           __
--    / _ |__ __/ /____  ___ / /____ _____/ /_
--   / __ / // / __/ _ \(_-</ __/ _ `/ __/ __/
--  /_/ |_\_,_/\__/\___/___/\__/\_,_/_/  \__/

-- by ae. Orlando
-- Author: ae Orland
-- GitHub: https://github.com/ae-orlando
-- _______________________________________________________________________

hl.on("hyprland.start", function()
    -- Cursor theme/size come from env.lua (XCURSOR_* + HYPRCURSOR_*); do not
    hl.exec_cmd("~/.config/swaync/scripts/clipboard.py watch") -- private, singleton clipboard capture
    hl.exec_cmd("hypridle") -- idle / lock / dpms
    hl.exec_cmd("hyprsunset") -- blue-light filter daemon (toggle with SUPER+N)
    hl.exec_cmd("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1") -- GUI privilege prompts
    hl.exec_cmd("nm-applet --indicator") -- network tray icon
    hl.exec_cmd("awww-daemon") -- wallpaper daemon (swww renamed to awww)
    -- Recover palette files before starting either themed daemon, then restore
    -- the last successful wallpaper. Never run recovery/restarts on a reload.
    hl.exec_cmd("~/.config/hypr/scripts/start-themed-desktop.sh")
end)

-- Autostart: apps launched once with the compositor.
-- by ae. Orlando
-- _______________________________________________________________________

hl.on("hyprland.start", function()
    hl.exec_cmd("hyprctl setcursor Bibata-Modern-Classic 24")               -- cursor theme
    hl.exec_cmd("waybar")                                            -- status bar
    hl.exec_cmd("swaync")                                              -- notifications
    hl.exec_cmd("hypridle")                                          -- idle / lock / dpms
    hl.exec_cmd("hyprsunset")                                        -- blue-light filter daemon (toggle with SUPER+N)
    hl.exec_cmd("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1") -- GUI privilege prompts
    hl.exec_cmd("nm-applet --indicator")                             -- network tray icon
    hl.exec_cmd("awww-daemon")                                       -- wallpaper daemon (swww renamed to awww)
    -- Wallpaper + system palette (matugen). Restores last wallpaper or default.
    hl.exec_cmd("sh -c 'sleep 1 && ~/.config/hypr/scripts/set-wall.sh'")
end)

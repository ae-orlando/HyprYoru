--     __  ___          _ __
--    /  |/  /__  ___  (_) /____  _______
--   / /|_/ / _ \/ _ \/ / __/ _ \/ __(_-<
--  /_/  /_/\___/_//_/_/\__/\___/_/ /___/

-- Primary output + fallback for anything else hot-plugged.
-- eDP-1 is this machine's laptop panel: adjust mode/scale per machine. The
-- empty-output rule below is the fallback, so hot-plugged or different
-- outputs still get a sane mode without editing this file.
-- By ae. Orlando
-- _______________________________________________________________________

-- https://wiki.hypr.land/Configuring/Basics/Monitors/
hl.monitor({
    output = "eDP-1",
    mode = "1920x1080@60.02",
    position = "0x0",
    scale = "1",
})

-- Fallback for any other / hot-plugged monitor.
hl.monitor({
    output = "",
    mode = "preferred",
    position = "auto",
    scale = "auto",
})

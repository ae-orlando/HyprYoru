--     ____               __
--    /  _/__  ___  __ __/ /_
--   _/ // _ \/ _ \/ // / __/
--  /___/_//_/ .__/\_,_/\__/
--          /_/
-- Input: keyboard, touchpad, gestures.
-- By ae. Orlando
-- _______________________________________________________________________

-- https://wiki.hypr.land/Configuring/Basics/Variables/

hl.config({
    input = {
        kb_layout = "us",
        kb_variant = "",
        kb_model = "",
        kb_options = "",
        kb_rules = "",

        repeat_rate = 25,

        follow_mouse = 1,

        sensitivity = 0, -- -1.0 - 1.0, 0 means no modification.

        touchpad = {
            natural_scroll = true,
            tap_to_click = true,
        },
    },
})

hl.gesture({
    fingers = 3,
    direction = "horizontal",
    action = "workspace",
})

-- Per-device tweaks (sensitivity, accel_profile, ...). None configured.
-- https://wiki.hypr.land/Configuring/Advanced-and-Cool/Devices/

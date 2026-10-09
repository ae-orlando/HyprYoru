-- Layout settings (one block per enabled layout).
-- https://wiki.hypr.land/Configuring/Basics/Variables/

-- Dwindle (https://wiki.hypr.land/Configuring/Layouts/Dwindle-Layout/)
hl.config({
    dwindle = {
        preserve_split = true, -- You probably want this
    },
})

-- Master (https://wiki.hypr.land/Configuring/Layouts/Master-Layout/)
hl.config({
    master = {
        new_status = "master",
    },
})

-- Scrolling (https://wiki.hypr.land/Configuring/Layouts/Scrolling-Layout/)
hl.config({
    scrolling = {
        fullscreen_on_one_column = true,
    },
})
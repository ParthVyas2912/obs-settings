obs = obslua

-- Settings
source_name = "Text"
pulse_speed = 2 -- Seconds for full fade in/out

-- Variables
local current_opacity = 1.0
local fade_direction = -1

function script_description()
    return "Pulse effect for text opacity."
end

function script_tick(seconds)
    local source = obs.obs_get_source_by_name(source_name)
    if source ~= nil then
        current_opacity = current_opacity + (fade_direction * (seconds / pulse_speed))
        if current_opacity <= 0 then
            fade_direction = 1
            current_opacity = 0
        elseif current_opacity >= 1 then
            fade_direction = -1
            current_opacity = 1
        end
        local settings = obs.obs_data_create()
        obs.obs_data_set_double(settings, "opacity", current_opacity)
        obs.obs_source_update(source, settings)
        obs.obs_data_release(settings)
        obs.obs_source_release(source)
    end
end

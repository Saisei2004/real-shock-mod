local STATUS_FILE = "re9_hp_web_status.json"
local CONFIG_FILE = "re9_hp_web_config.json"
local BRIDGE_VERSION = 6

local default_config = {
    enabled = true,
    write_interval = 0.10,
    hp_reader = {
        enabled = true,
        note = "RE9 app.CharacterManager -> PlayerContextFast -> HitPoint の軽量読み取り。",
        low_hp_percent = 30,
        roots = {
            "app.CharacterManager",
        },
        object_methods = {
            "get_PlayerContextFast",
            "getPlayerContextRefFast",
        },
        nested_methods = {
            "get_HitPoint",
        },
        hp_members = {
            "get_CurrentHitPoint",
        },
        max_hp_members = {
            "get_CurrentMaximumHitPoint",
        },
    },
}

local state = {
    last_write = 0.0,
    last_hp = nil,
    last_damage = nil,
    damage_count = 0,
}

local function merge_defaults(target, defaults)
    if target == nil then
        return defaults
    end
    for key, value in pairs(defaults) do
        if target[key] == nil then
            target[key] = value
        elseif type(target[key]) == "table" and type(value) == "table" then
            merge_defaults(target[key], value)
        end
    end
    return target
end

local function load_config()
    local cfg = json.load_file(CONFIG_FILE)
    if cfg == nil then
        json.dump_file(CONFIG_FILE, default_config, 4)
        return default_config
    end
    cfg = merge_defaults(cfg, default_config)
    json.dump_file(CONFIG_FILE, cfg, 4)
    return cfg
end

local config = load_config()

local function dump_status(payload)
    json.dump_file(STATUS_FILE, payload, 0)
end

local function write_error_status(message)
    dump_status({
        schema_version = 1,
        bridge_version = BRIDGE_VERSION,
        game = "Resident Evil Requiem",
        source = "REFramework Lua bridge",
        mode = "safe-config-only",
        phase = "error",
        timestamp = os.time(),
        error = tostring(message),
        player_found = false,
        diagnostics = {
            bridge = "safe-config-only",
            note = "Lua bridge failed while updating status.",
        },
    })
end

dump_status({
    schema_version = 1,
    bridge_version = BRIDGE_VERSION,
    game = "Resident Evil Requiem",
    source = "REFramework Lua bridge",
    mode = "safe-config-only",
    phase = "loaded",
    timestamp = os.time(),
    player_found = false,
    diagnostics = {
        bridge = "safe-config-only",
        note = "Lua bridge loaded and is waiting for frame updates.",
    },
})

local function safe_call(fn)
    local ok, value = pcall(fn)
    if ok then
        return value
    end
    return nil
end

local function read_member(obj, member)
    if obj == nil or member == nil or member == "" then
        return nil
    end
    if string.sub(member, 1, 4) == "get_" then
        return safe_call(function()
            return obj:call(member)
        end)
    end
    local value = safe_call(function()
        return obj:get_field(member)
    end)
    if value ~= nil then
        return value
    end
    return safe_call(function()
        return obj[member]
    end)
end

local function first_number(obj, members)
    for _, member in ipairs(members or {}) do
        local value = read_member(obj, member)
        if type(value) == "number" then
            return value, member
        end
    end
    return nil, nil
end

local function percent_from_threshold(value, max_hp)
    if type(value) ~= "number" then
        return nil
    end
    if value <= 1.0 then
        return value * 100.0
    end
    if max_hp ~= nil and max_hp > 0 then
        return value / max_hp * 100.0
    end
    return value
end

local function classify_vital(hp_percent, max_hp, context, reader)
    local low_hp_percent = reader.low_hp_percent or 30
    local vital_raw = read_member(context, "get_HitPointVital")
    local bottom_danger = read_member(context, "get_BottomOfVitalDanger")
    local bottom_caution = read_member(context, "get_BottomOfVitalCaution")
    local bottom_fine = read_member(context, "get_BottomOfVitalFine")
    local danger_percent = percent_from_threshold(bottom_danger, max_hp)
    local caution_percent = percent_from_threshold(bottom_caution, max_hp) or danger_percent or low_hp_percent
    local fine_percent = percent_from_threshold(bottom_fine, max_hp)

    local stage = "unknown"
    local low_hp = false
    local faltering_low_hp = false
    local stage_source = "unknown"

    if type(vital_raw) == "number" then
        stage_source = "vital"
        if vital_raw >= 2 then
            stage = "danger"
            low_hp = true
            faltering_low_hp = true
        elseif vital_raw == 1 then
            stage = "caution"
            low_hp = true
        elseif vital_raw == 0 then
            stage = "fine"
        end
    end

    if hp_percent ~= nil then
        if danger_percent ~= nil and hp_percent <= danger_percent then
            stage = "danger"
            low_hp = true
            faltering_low_hp = true
            stage_source = "bottom_danger"
        elseif hp_percent <= caution_percent then
            stage = "caution"
            low_hp = true
            stage_source = bottom_caution ~= nil and "bottom_caution" or "fallback"
        elseif fine_percent ~= nil and hp_percent <= fine_percent then
            stage = "fine"
            stage_source = "bottom_fine"
        elseif stage == "unknown" then
            stage = "fine"
            stage_source = "hp_percent"
        end
    end

    return {
        low_hp = low_hp,
        faltering_low_hp = faltering_low_hp,
        low_hp_stage = stage,
        low_hp_stage_source = stage_source,
        vital_raw = vital_raw,
        bottom_danger = bottom_danger,
        bottom_caution = bottom_caution,
        bottom_fine = bottom_fine,
        danger_percent = danger_percent,
        caution_percent = caution_percent,
        fine_percent = fine_percent,
        fallback_low_hp_percent = low_hp_percent,
    }
end

local function read_re9_fast_path(reader, diagnostics)
    local manager = sdk.get_managed_singleton("app.CharacterManager")
    table.insert(diagnostics.roots_checked, {
        root = "app.CharacterManager.fast_path",
        found = manager ~= nil,
        objects_checked = manager ~= nil and 2 or 0,
    })
    if manager == nil then
        return nil
    end

    local context = read_member(manager, "get_PlayerContextFast") or read_member(manager, "getPlayerContextRefFast")
    if context == nil then
        return nil
    end

    local hitpoint = read_member(context, "get_HitPoint")
    if hitpoint == nil then
        return nil
    end

    local hp = read_member(hitpoint, "get_CurrentHitPoint")
    local max_hp = read_member(hitpoint, "get_CurrentMaximumHitPoint")
    if type(hp) ~= "number" then
        return nil
    end

    local hp_percent = max_hp ~= nil and max_hp > 0 and (hp / max_hp * 100.0) or nil
    local vital = classify_vital(hp_percent, max_hp, context, reader)

    return {
        player_found = true,
        hp = hp,
        max_hp = max_hp,
        hp_percent = hp_percent,
        reader = "app.CharacterManager.fast_path",
        hp_member = "get_CurrentHitPoint",
        max_hp_member = "get_CurrentMaximumHitPoint",
        low_hp = vital.low_hp,
        faltering_low_hp = vital.faltering_low_hp,
        low_hp_stage = vital.low_hp_stage,
        low_hp_stage_source = vital.low_hp_stage_source,
        vital_raw = vital.vital_raw,
        bottom_danger = vital.bottom_danger,
        bottom_caution = vital.bottom_caution,
        bottom_fine = vital.bottom_fine,
        danger_percent = vital.danger_percent,
        caution_percent = vital.caution_percent,
        fine_percent = vital.fine_percent,
        fallback_low_hp_percent = vital.fallback_low_hp_percent,
        diagnostics = diagnostics,
    }
end

local function build_candidates(root, reader)
    local objects = {}
    if root ~= nil then
        table.insert(objects, root)
    end

    for _, method in ipairs(reader.object_methods or {}) do
        local obj = read_member(root, method)
        if obj ~= nil then
            table.insert(objects, obj)
        end
    end

    local original_count = #objects
    for index = 1, original_count do
        local obj = objects[index]
        for _, method in ipairs(reader.nested_methods or {}) do
            local nested = read_member(obj, method)
            if nested ~= nil then
                table.insert(objects, nested)
            end
        end
    end

    return objects
end

local function read_hp()
    local reader = config.hp_reader or {}
    local diagnostics = {
        bridge = "safe-config-only",
        note = "HP読み取りは設定駆動のみ。自動探索はしません。",
        hp_reader_enabled = reader.enabled == true,
        roots_checked = {},
    }

    if reader.enabled ~= true then
        return {
            player_found = false,
            hp = nil,
            max_hp = nil,
            hp_percent = nil,
            reader = nil,
            diagnostics = diagnostics,
        }
    end

    local fast_result = read_re9_fast_path(reader, diagnostics)
    if fast_result ~= nil then
        return fast_result
    end

    for _, root_name in ipairs(reader.roots or {}) do
        local root = sdk.get_managed_singleton(root_name)
        local root_info = {
            root = root_name,
            found = root ~= nil,
            objects_checked = 0,
        }
        table.insert(diagnostics.roots_checked, root_info)

        if root ~= nil then
            local objects = build_candidates(root, reader)
            root_info.objects_checked = #objects
            for _, obj in ipairs(objects) do
                local hp, hp_member = first_number(obj, reader.hp_members)
                if hp ~= nil then
                    local max_hp, max_hp_member = first_number(obj, reader.max_hp_members)
                    local hp_percent = max_hp ~= nil and max_hp > 0 and (hp / max_hp * 100.0) or nil
                    local vital = classify_vital(hp_percent, max_hp, nil, reader)
                    return {
                        player_found = true,
                        hp = hp,
                        max_hp = max_hp,
                        hp_percent = hp_percent,
                        reader = root_name,
                        hp_member = hp_member,
                        max_hp_member = max_hp_member,
                        low_hp = vital.low_hp,
                        faltering_low_hp = vital.faltering_low_hp,
                        low_hp_stage = vital.low_hp_stage,
                        low_hp_stage_source = vital.low_hp_stage_source,
                        vital_raw = vital.vital_raw,
                        bottom_danger = vital.bottom_danger,
                        bottom_caution = vital.bottom_caution,
                        bottom_fine = vital.bottom_fine,
                        danger_percent = vital.danger_percent,
                        caution_percent = vital.caution_percent,
                        fine_percent = vital.fine_percent,
                        fallback_low_hp_percent = vital.fallback_low_hp_percent,
                        diagnostics = diagnostics,
                    }
                end
            end
        end
    end

    return {
        player_found = false,
        hp = nil,
        max_hp = nil,
        hp_percent = nil,
        reader = nil,
        diagnostics = diagnostics,
    }
end

local function write_status()
    local result = read_hp()
    local hp = result.hp

    if hp ~= nil and state.last_hp ~= nil and hp < state.last_hp then
        state.last_damage = state.last_hp - hp
        state.damage_count = state.damage_count + 1
    end
    if hp ~= nil then
        state.last_hp = hp
    end

    dump_status({
        schema_version = 1,
        bridge_version = BRIDGE_VERSION,
        game = "Resident Evil Requiem",
        source = "REFramework Lua bridge",
        mode = "safe-config-only",
        phase = "running",
        timestamp = os.time(),
        player_found = result.player_found,
        hp = result.hp,
        max_hp = result.max_hp,
        hp_percent = result.hp_percent,
        low_hp = result.low_hp,
        faltering_low_hp = result.faltering_low_hp,
        low_hp_stage = result.low_hp_stage,
        low_hp_stage_source = result.low_hp_stage_source,
        vital_raw = result.vital_raw,
        bottom_danger = result.bottom_danger,
        bottom_caution = result.bottom_caution,
        bottom_fine = result.bottom_fine,
        danger_percent = result.danger_percent,
        caution_percent = result.caution_percent,
        fine_percent = result.fine_percent,
        fallback_low_hp_percent = result.fallback_low_hp_percent,
        reader = result.reader,
        hp_member = result.hp_member,
        max_hp_member = result.max_hp_member,
        last_damage = state.last_damage,
        damage_count = state.damage_count,
        diagnostics = result.diagnostics,
    }, 0)
end

re.on_frame(function()
    if config.enabled ~= true then
        return
    end

    local now = os.clock()
    local interval = config.write_interval or 1.0
    if now - state.last_write < interval then
        return
    end
    state.last_write = now
    local ok, err = pcall(write_status)
    if not ok then
        write_error_status(err)
    end
end)

if log ~= nil then
    log.info("[RE9 HP Web] safe bridge v" .. tostring(BRIDGE_VERSION) .. " loaded. HP reader is config-only.")
end

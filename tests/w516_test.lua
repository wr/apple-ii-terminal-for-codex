-- W-516 smoke test: boot the 8-bit client, Connect, Ctrl-C back to the
-- menu, Connect again, /exit back to the menu. Prints PASS/FAIL lines.
local mac = manager.machine
local kbd = mac.natkeyboard
local mem = mac.devices[":maincpu"].spaces["program"]

local function screen_text()
  -- decode text page 1 ($0400-$07F7), high bit masked
  local rows = {}
  local bases = {}
  for r = 0, 23 do
    local lo = {0x00,0x80,0x00,0x80,0x00,0x80,0x00,0x80,
                0x28,0xA8,0x28,0xA8,0x28,0xA8,0x28,0xA8,
                0x50,0xD0,0x50,0xD0,0x50,0xD0,0x50,0xD0}
    local hi = {0x04,0x04,0x05,0x05,0x06,0x06,0x07,0x07,
                0x04,0x04,0x05,0x05,0x06,0x06,0x07,0x07,
                0x04,0x04,0x05,0x05,0x06,0x06,0x07,0x07}
    local base = hi[r+1]*256 + lo[r+1]
    local s = {}
    for c = 0, 39 do
      local b = mem:read_u8(base + c) & 0x7F
      if b < 0x20 then b = b + 0x40 end  -- inverse caps fold roughly to caps
      s[#s+1] = string.char(b)
    end
    rows[#rows+1] = table.concat(s)
  end
  return table.concat(rows, "\n")
end

local function on_menu()
  local t = screen_text():upper()
  return t:find("1. CONNECT", 1, true) ~= nil
end

local function in_session()
  -- the session input row shows "> " and the menu is gone
  return not on_menu()
end

-- Ctrl-C has no natkeyboard mapping; press the real matrix keys instead
local function find_field(want)
  for _, port in pairs(mac.ioport.ports) do
    for fname, field in pairs(port.fields) do
      if fname == want then return field end
    end
  end
end
local f_ctrl = find_field("Control")
local f_c = find_field("c  C")

local aframe = 0       -- absolute frame clock, never reset
local ctrlc_at = nil   -- aframe the Ctrl-C press starts, nil = idle
local function ctrl_c() ctrlc_at = aframe + 1 end
local function ctrl_c_tick()
  if not ctrlc_at then return end
  local dt = aframe - ctrlc_at
  if dt == 0 then f_ctrl:set_value(1)
  elseif dt == 4 then f_c:set_value(1)
  elseif dt == 16 then f_c:clear_value()
  elseif dt == 20 then f_ctrl:clear_value(); ctrlc_at = nil
  end
end

local frame = 0
local step = 1
local deadline = 60 * 240   -- give the whole run 4 emulated minutes
local fails = 0

local function say(s) print("W516TEST: " .. s) end

local function dump(tag)
  print("W516TEST: ---- screen at " .. tag .. " ----")
  for line in screen_text():gmatch("[^\n]+") do
    print("W516TEST: |" .. line .. "|")
  end
end

emu.register_frame_done(function()
  frame = frame + 1
  aframe = aframe + 1
  ctrl_c_tick()
  if frame > deadline then
    say("FAIL timeout in step " .. step)
    mac:exit()
    return
  end

  if step == 1 then
    -- wait for the boot menu
    if frame % 30 == 0 and on_menu() then
      say("menu up at frame " .. frame)
      kbd:post("1")               -- Connect
      step = 2; frame = 0
    end
  elseif step == 2 then
    -- dial window (~4s of theater) then session; give it 12s
    if frame == 60 * 12 then
      if in_session() then
        say("PASS session entered")
      else
        say("FAIL no session after Connect"); fails = fails + 1
      end
      if not (f_ctrl and f_c) then say("FAIL no Control/C ioport fields"); mac:exit() end
      ctrl_c()                    -- Ctrl-C while idle
      step = 3; frame = 0
    end
  elseif step == 3 then
    if frame == 60 * 3 then
      if on_menu() then
        say("PASS Ctrl-C idle returned to menu")
      else
        say("FAIL Ctrl-C did not return to menu"); fails = fails + 1
        dump("after Ctrl-C")
      end
      kbd:post("1")               -- Connect again (also exercises dcd path)
      step = 4; frame = 0
    end
  elseif step == 4 then
    if frame == 60 * 12 then
      if in_session() then
        say("PASS re-entered session")
      else
        say("FAIL no session on reconnect"); fails = fails + 1
      end
      kbd:post("/exit\n")
      step = 5; frame = 0
    end
  elseif step == 5 then
    if frame == 60 * 4 then
      if on_menu() then
        say("PASS /exit returned to menu")
      else
        say("FAIL /exit did not return to menu"); fails = fails + 1
      end
      say(fails == 0 and "ALL PASS" or ("DONE with " .. fails .. " failures"))
      mac:exit()
    end
  end
end)

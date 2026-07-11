-- W-517 test: Connect against a fake modem that answers 0.5s in.
-- CONNECT mode: expect still "Dialing" at +2s (theater rings out), session by +9s.
-- BUSY mode: expect "Dial failed" by +3s (failures still cut immediately).
local mac = manager.machine
local kbd = mac.natkeyboard
local mem = mac.devices[":maincpu"].spaces["program"]
local mode = os.getenv("W517MODE") or "CONNECT"

local function screen_text()
  local rows = {}
  local lo = {0x00,0x80,0x00,0x80,0x00,0x80,0x00,0x80,
              0x28,0xA8,0x28,0xA8,0x28,0xA8,0x28,0xA8,
              0x50,0xD0,0x50,0xD0,0x50,0xD0,0x50,0xD0}
  local hi = {0x04,0x04,0x05,0x05,0x06,0x06,0x07,0x07,
              0x04,0x04,0x05,0x05,0x06,0x06,0x07,0x07,
              0x04,0x04,0x05,0x05,0x06,0x06,0x07,0x07}
  for r = 0, 23 do
    local base = hi[r+1]*256 + lo[r+1]
    local s = {}
    for c = 0, 39 do
      local b = mem:read_u8(base + c) & 0x7F
      if b < 0x20 then b = b + 0x40 end
      s[#s+1] = string.char(b)
    end
    rows[#rows+1] = table.concat(s)
  end
  return table.concat(rows, "\n"):upper()
end

local function say(s) print("W517TEST: " .. s) end
local frame, step = 0, 1
local fails = 0

emu.register_frame_done(function()
  frame = frame + 1
  if frame > 60 * 240 then say("FAIL timeout step " .. step); mac:exit() end
  if step == 1 then
    if frame % 30 == 0 and screen_text():find("1. CONNECT", 1, true) then
      say("menu up; mode=" .. mode)
      kbd:post("1")
      step = 2; frame = 0
    end
  elseif step == 2 then
    if frame == 60 * 2 then
      local t = screen_text()
      if mode == "CONNECT" then
        -- verdict landed early; at +2s the theater must still be going
        -- (the menu stays on screen during the dial - only session_start
        -- clears it, so DIALING alongside the menu is the dial window)
        if t:find("DIALING", 1, true) then
          say("PASS still in dial theater at +2s (ring-out, not hard cut)")
        else
          say("FAIL not in dial window at +2s"); fails = fails + 1
        end
      else
        if t:find("DIAL FAILED", 1, true) then
          say("PASS BUSY cut the dial immediately")
        else
          say("FAIL no 'Dial failed' after BUSY"); fails = fails + 1
        end
      end
      step = 3; frame = 0
    end
  elseif step == 3 then
    if frame == 60 * 8 then
      local t = screen_text()
      if mode == "CONNECT" then
        if not t:find("DIALING", 1, true) and not t:find("1. CONNECT", 1, true) then
          say("PASS session entered after the theater ended")
        else
          say("FAIL never reached the session"); fails = fails + 1
        end
      else
        if t:find("1. CONNECT", 1, true) then
          say("PASS back on the menu after the failed dial")
        else
          say("FAIL not back on the menu"); fails = fails + 1
        end
      end
      say(fails == 0 and "ALL PASS" or "DONE with failures")
      mac:exit()
    end
  end
end)

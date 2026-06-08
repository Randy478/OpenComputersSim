-- OpenComputersSim bootstrap: a slim re-implementation of OpenComputers'
-- machine.lua. It installs the "bubbling" coroutine library so that a system
-- yield from computer.pullSignal propagates up through every nested OpenOS
-- process coroutine to the host driver, then wires the component/computer/
-- unicode globals to the Python host and runs the EEPROM BIOS.
--
-- The Python side passes in the host bridge as the single vararg.

local host = ...

-------------------------------------------------------------------------------
-- Capture the real coroutine library before we shadow it.
-------------------------------------------------------------------------------
local real = {
  create = coroutine.create,
  resume = coroutine.resume,
  yield = coroutine.yield,
  status = coroutine.status,
  running = coroutine.running,
  isyieldable = coroutine.isyieldable,
  wrap = coroutine.wrap,
}

-------------------------------------------------------------------------------
-- checkArg: argument type checking helper used throughout OpenOS.
-------------------------------------------------------------------------------
function checkArg(n, have, ...)
  have = type(have)
  local function check(want, ...)
    if not want then
      return false
    else
      return have == want or check(...)
    end
  end
  if not check(...) then
    local msg = string.format("bad argument #%d (%s expected, got %s)",
                              n, table.concat({...}, " or "), have)
    error(msg, 3)
  end
end

-- Lua 5.3's os.date rejects floats with a fractional part. OpenComputers'
-- sandbox tolerates them, so floor any numeric timestamp first.
do
  local rawdate = os.date
  os.date = function(format, time)
    if type(time) == "number" then time = math.floor(time) end
    return rawdate(format, time)
  end
end

-------------------------------------------------------------------------------
-- Bubbling coroutine library (port of machine.lua's sandbox.coroutine).
-- A "user" yield is tagged with a leading nil; a "system" yield (from
-- computer.pullSignal) carries a non-nil value and is re-yielded upward.
-------------------------------------------------------------------------------
local sandbox_coroutine
sandbox_coroutine = {
  create = real.create,
  running = real.running,
  status = real.status,
  isyieldable = real.isyieldable,
  resume = function(co, ...)
    local args = table.pack(...)
    while true do
      local result = table.pack(real.resume(co, table.unpack(args, 1, args.n)))
      if not result[1] then
        return false, result[2]
      elseif real.status(co) == "dead" then
        return true, table.unpack(result, 2, result.n)
      elseif result[2] ~= nil then
        -- system yield: bubble it up toward the host driver
        args = table.pack(real.yield(result[2]))
      else
        -- user yield
        return true, table.unpack(result, 3, result.n)
      end
    end
  end,
  yield = function(...)
    return real.yield(nil, ...)
  end,
  wrap = function(f)
    local co = real.create(f)
    return function(...)
      local result = table.pack(sandbox_coroutine.resume(co, ...))
      if not result[1] then
        error(result[2], 0)
      end
      return table.unpack(result, 2, result.n)
    end
  end,
}
coroutine = sandbox_coroutine

-------------------------------------------------------------------------------
-- unicode library (utf-8 aware, with simple wide-character handling).
-------------------------------------------------------------------------------
local function is_wide(cp)
  return (cp >= 0x1100 and cp <= 0x115F) or
         (cp >= 0x2E80 and cp <= 0x303E) or
         (cp >= 0x3041 and cp <= 0x33FF) or
         (cp >= 0x3400 and cp <= 0x4DBF) or
         (cp >= 0x4E00 and cp <= 0x9FFF) or
         (cp >= 0xA000 and cp <= 0xA4CF) or
         (cp >= 0xAC00 and cp <= 0xD7A3) or
         (cp >= 0xF900 and cp <= 0xFAFF) or
         (cp >= 0xFE30 and cp <= 0xFE4F) or
         (cp >= 0xFF00 and cp <= 0xFF60) or
         (cp >= 0xFFE0 and cp <= 0xFFE6)
end

unicode = {}
function unicode.char(...)
  return utf8.char(...)
end
function unicode.len(s)
  return utf8.len(s) or #s
end
function unicode.sub(s, i, j)
  local n = utf8.len(s)
  if not n then return string.sub(s, i, j) end
  i = i or 1
  j = j or -1
  if i < 0 then i = n + i + 1 end
  if j < 0 then j = n + j + 1 end
  if i < 1 then i = 1 end
  if j > n then j = n end
  if i > j then return "" end
  local bi = utf8.offset(s, i)
  local bj = utf8.offset(s, j + 1)
  if not bi then return "" end
  return string.sub(s, bi, bj and bj - 1 or #s)
end
function unicode.upper(s) return string.upper(s) end
function unicode.lower(s) return string.lower(s) end
function unicode.reverse(s)
  local r = {}
  for _, cp in utf8.codes(s) do
    table.insert(r, 1, utf8.char(cp))
  end
  return table.concat(r)
end
function unicode.charWidth(s)
  if s == nil or s == "" then return 0 end
  local cp = utf8.codepoint(s, 1)
  return is_wide(cp) and 2 or 1
end
function unicode.isWide(s)
  return unicode.charWidth(s) > 1
end
function unicode.wlen(s)
  local w = 0
  for _, cp in utf8.codes(s) do
    w = w + (is_wide(cp) and 2 or 1)
  end
  return w
end
function unicode.wtrunc(s, count)
  local w = 0
  local result = {}
  for _, cp in utf8.codes(s) do
    local cw = is_wide(cp) and 2 or 1
    if w + cw >= count then break end
    w = w + cw
    result[#result + 1] = utf8.char(cp)
  end
  return table.concat(result)
end

-------------------------------------------------------------------------------
-- component API. The Python host provides the primitive operations; we build
-- list/proxy/type/slot/methods/doc/fields on top, exactly as OpenOS expects.
-------------------------------------------------------------------------------
component = {}

function component.list(filter, exact)
  local res = host.list_components(filter, exact)
  local key = nil
  return setmetatable(res, {__call = function()
    local k, v = next(res, key)
    key = k
    return k, v
  end})
end

function component.invoke(address, method, ...)
  return host.invoke(address, method, ...)
end

function component.type(address)
  return host.ctype(address)
end

function component.slot(address)
  return host.slot(address)
end

function component.methods(address)
  return host.methods(address)
end

function component.doc(address, method)
  return host.doc(address, method)
end

function component.fields(address)
  return host.fields(address)
end

function component.proxy(address)
  local ctype = host.ctype(address)
  if not ctype then
    return nil, "no such component"
  end
  local proxy = {address = address, type = ctype, slot = host.slot(address)}
  local methods = host.methods(address)
  for name in pairs(methods) do
    proxy[name] = function(...)
      return host.invoke(address, name, ...)
    end
  end
  local fields = host.fields(address)
  if fields then
    for name in pairs(fields) do
      if proxy[name] == nil then
        proxy[name] = host.field_get(address, name)
      end
    end
  end
  return proxy
end

-------------------------------------------------------------------------------
-- computer API.
-------------------------------------------------------------------------------
computer = {}

function computer.pullSignal(timeout)
  local sig = real.yield(timeout == nil and math.huge or timeout)
  if sig == nil then
    return
  end
  return table.unpack(sig, 1, sig.n or #sig)
end

function computer.pushSignal(name, ...)
  return host.push_signal(name, ...)
end

function computer.uptime() return host.uptime() end
function computer.realTime() return host.real_time() end
function computer.address() return host.computer_address() end
function computer.tmpAddress() return host.tmp_address() end
function computer.freeMemory() return math.floor(host.free_memory()) end
function computer.totalMemory() return math.floor(host.total_memory()) end
function computer.energy() return host.energy() end
function computer.maxEnergy() return host.max_energy() end
function computer.getBootAddress() return host.get_boot_address() end
function computer.setBootAddress(addr) return host.set_boot_address(addr) end
function computer.beep(freq, duration) return host.beep(freq, duration) end
function computer.getDeviceInfo() return host.get_device_info() end
function computer.getProgramLocation() return "/init.lua" end
function computer.getProgramLocations() return {} end
function computer.getArchitecture() return "Lua 5.3" end
function computer.getArchitectures() return {"Lua 5.3"} end
function computer.setArchitecture() return false end
function computer.isRunning() return true end
function computer.start() return false end
function computer.stop() return host.shutdown(false) end

-- User management (single-user sandbox).
local users = {}
function computer.users() return table.unpack(users) end
function computer.addUser(name) users[#users + 1] = name; return true end
function computer.removeUser(name)
  for i, u in ipairs(users) do
    if u == name then table.remove(users, i); return true end
  end
  return false
end

function computer.shutdown(reboot)
  return host.shutdown(reboot and true or false)
end

-------------------------------------------------------------------------------
-- Boot entry: run the EEPROM BIOS, which loads and runs /init.lua.
-------------------------------------------------------------------------------
local function machine_main()
  local eeprom = component.list("eeprom")()
  local bios = component.invoke(eeprom, "get")
  local fn, err = load(bios, "=bios")
  if not fn then
    error("failed to load BIOS: " .. tostring(err), 0)
  end
  return fn()
end

return {
  main = machine_main,
  real = real,
}

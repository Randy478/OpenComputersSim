"""EEPROM component holding the Lua BIOS and boot configuration data."""

from __future__ import annotations

import zlib

from .base import Component, method

# A faithful, minimal Lua BIOS: find the boot filesystem and run /init.lua.
# OpenComputersSim boots /init.lua directly, but a real BIOS is exposed so that
# the `flash` tool and eeprom inspection behave like the real mod.
DEFAULT_BIOS = """\
-- Capture as locals so the closures survive boot.lua clearing the globals.
local component = component
local computer = computer
local eeprom = component.list("eeprom")()
computer.getBootAddress = function()
  return component.invoke(eeprom, "getData")
end
computer.setBootAddress = function(address)
  return component.invoke(eeprom, "setData", address)
end
do
  local screen = component.list("screen")()
  local gpu = component.list("gpu")()
  if gpu and screen then
    component.invoke(gpu, "bind", screen)
  end
end
local function tryLoadFrom(address)
  local handle, reason = component.invoke(address, "open", "/init.lua")
  if not handle then return nil, reason end
  local buffer = ""
  repeat
    local data, reason = component.invoke(address, "read", handle, math.huge)
    if not data and reason then return nil, reason end
    buffer = buffer .. (data or "")
  until not data
  component.invoke(address, "close", handle)
  return load(buffer, "=init")
end
local init, reason
if computer.getBootAddress() then
  init, reason = tryLoadFrom(computer.getBootAddress())
end
if not init then
  computer.setBootAddress()
  for address in component.list("filesystem") do
    init, reason = tryLoadFrom(address)
    if init then
      computer.setBootAddress(address)
      break
    end
  end
end
if not init then error("no bootable medium found" .. (reason and (": " .. tostring(reason)) or ""), 0) end
return init()
"""


class EEPROM(Component):
    ctype = "eeprom"

    def __init__(self, host, code: str = DEFAULT_BIOS, data: str = "", address=None):
        super().__init__(host, address)
        self.code = code
        self.data = data
        self.label = "EEPROM (Lua BIOS)"
        self.readonly = False

    @method("Get the currently stored byte array (BIOS code).")
    def get(self):
        return self.code

    @method("Overwrite the currently stored byte array.")
    def set(self, data):
        if self.readonly:
            return None, "storage is readonly"
        self.code = data or ""
        return True

    @method("Get the label of the EEPROM.")
    def getLabel(self):
        return self.label

    @method("Set the label of the EEPROM.")
    def setLabel(self, value):
        self.label = str(value)[:24]
        return self.label

    @method("Get the storage capacity of this EEPROM.")
    def getSize(self):
        return 4096

    @method("Get the size of the volatile data storage area.")
    def getDataSize(self):
        return 256

    @method("Get the currently stored volatile data (boot address).")
    def getData(self):
        return self.data

    @method("Overwrite the currently stored volatile data.")
    def setData(self, data):
        self.data = data if data is not None else ""
        return True

    @method("Get the checksum of the data on this EEPROM.")
    def getChecksum(self):
        return format(zlib.crc32((self.code + self.data).encode("utf-8")) & 0xFFFFFFFF, "08x")

    @method("Make this EEPROM read-only. This cannot be undone.")
    def makeReadonly(self, checksum):
        if checksum == self.getChecksum():
            self.readonly = True
            return True
        return None, "incorrect checksum"

    def device_info(self):
        return {
            "class": "memory",
            "description": "EEPROM",
            "vendor": "MightyPirates GmbH & Co. KG",
            "product": "FlashStick 4K",
            "capacity": "4096",
        }

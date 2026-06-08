"""Managed filesystem component backed by a host directory.

Each emulated hard drive maps to a directory on the host. Paths from the guest
are jailed inside that directory. Capacity is enforced against the configured
tier size so ``df`` reports realistic free space.
"""

from __future__ import annotations

import math
import os
import time

from .base import Component, method


class FileHandle:
    def __init__(self, fileobj, mode):
        self.f = fileobj
        self.mode = mode


class Filesystem(Component):
    ctype = "filesystem"

    def __init__(self, host, root: str, capacity: int, label: str = "",
                 readonly: bool = False, address=None, tier: str = "3"):
        super().__init__(host, address)
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)
        self.capacity = capacity
        self.label = label
        self.readonly = readonly
        self.tier = tier
        self._handles: dict[int, FileHandle] = {}
        self._next_handle = 1

    # -- path handling ------------------------------------------------------

    def _resolve(self, path: str) -> str:
        # Normalise the guest path and jail it inside root.
        path = (path or "/").replace("\\", "/")
        parts = []
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return os.path.join(self.root, *parts)

    # -- label / capacity ---------------------------------------------------

    @method("Get the current label of the file system.")
    def getLabel(self):
        return self.label or None

    @method("Set the label of the file system. Returns the new label.")
    def setLabel(self, value):
        if self.readonly:
            return None, "label is read only"
        self.label = str(value)[:16] if value is not None else ""
        return self.label

    @method("Returns whether the file system is read-only.")
    def isReadOnly(self):
        return self.readonly

    @method("The overall capacity of the file system, in bytes.")
    def spaceTotal(self):
        return self.capacity

    @method("The currently used capacity of the file system, in bytes.")
    def spaceUsed(self):
        total = 0
        for dirpath, _dirs, files in os.walk(self.root):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, name))
                except OSError:
                    pass
        return min(total, self.capacity)

    # -- queries ------------------------------------------------------------

    @method("Returns whether an object exists at the specified path.")
    def exists(self, path):
        return os.path.exists(self._resolve(path))

    @method("Returns whether the object at the specified path is a directory.")
    def isDirectory(self, path):
        return os.path.isdir(self._resolve(path))

    @method("Returns the size of the object at the specified path.")
    def size(self, path):
        p = self._resolve(path)
        if os.path.isfile(p):
            return os.path.getsize(p)
        return 0

    @method("Returns the (real world) timestamp of when the object was modified.")
    def lastModified(self, path):
        p = self._resolve(path)
        try:
            return int(os.path.getmtime(p) * 1000)
        except OSError:
            return 0

    @method("Returns a list of names of objects in the directory at the path.")
    def list(self, path):
        p = self._resolve(path)
        if not os.path.isdir(p):
            return None, "no such file or directory"
        names = []
        for name in sorted(os.listdir(p)):
            full = os.path.join(p, name)
            names.append(name + "/" if os.path.isdir(full) else name)
        return self.table(names)

    # -- mutations ----------------------------------------------------------

    @method("Creates a directory at the specified path.")
    def makeDirectory(self, path):
        if self.readonly:
            return None, "filesystem is readonly"
        p = self._resolve(path)
        if os.path.exists(p):
            return False
        try:
            os.makedirs(p)
            return True
        except OSError as e:
            return None, str(e)

    @method("Removes the object at the specified path.")
    def remove(self, path):
        if self.readonly:
            return None, "filesystem is readonly"
        p = self._resolve(path)
        try:
            if os.path.isdir(p):
                import shutil

                shutil.rmtree(p)
            elif os.path.exists(p):
                os.remove(p)
            else:
                return False
            return True
        except OSError:
            return False

    @method("Renames/moves an object from the first path to the second path.")
    def rename(self, frm, to):
        if self.readonly:
            return None, "filesystem is readonly"
        a, b = self._resolve(frm), self._resolve(to)
        if not os.path.exists(a):
            return False
        try:
            os.makedirs(os.path.dirname(b), exist_ok=True)
            os.replace(a, b)
            return True
        except OSError:
            return False

    # -- streams ------------------------------------------------------------

    @method("Opens a new file descriptor and returns its handle.")
    def open(self, path, mode="r"):
        mode = mode or "r"
        base = mode.replace("b", "")
        p = self._resolve(path)
        if base in ("w", "a") and self.readonly:
            return None, "filesystem is readonly"
        pymode = {"r": "rb", "w": "wb", "a": "ab"}.get(base)
        if pymode is None:
            return None, "unsupported mode"
        if base == "r" and not os.path.isfile(p):
            return None, path + ": no such file or directory"
        try:
            if base in ("w", "a"):
                os.makedirs(os.path.dirname(p), exist_ok=True)
            f = open(p, pymode)
        except OSError as e:
            return None, str(e)
        handle = self._next_handle
        self._next_handle += 1
        self._handles[handle] = FileHandle(f, base)
        return handle

    @method("Closes an open file descriptor with the specified handle.")
    def close(self, handle):
        h = self._handles.pop(int(handle), None)
        if h:
            h.f.close()
            return True
        return None, "bad file descriptor"

    @method("Reads up to the specified amount of data from an open descriptor.")
    def read(self, handle, count):
        h = self._handles.get(int(handle))
        if not h:
            return None, "bad file descriptor"
        if count is None or count == float("inf") or count > (1 << 30):
            # math.huge / math.maxinteger mean "read everything".
            data = h.f.read()
        else:
            data = h.f.read(int(count))
        if data == b"":
            return None  # EOF
        # Return raw bytes; lupa hands these to Lua as a byte-exact string.
        return data

    @method("Writes the specified data to an open descriptor.")
    def write(self, handle, value):
        h = self._handles.get(int(handle))
        if not h:
            return None, "bad file descriptor"
        if isinstance(value, str):
            # Lua strings arrive utf-8 decoded; re-encode to recover the bytes.
            value = value.encode("utf-8", "surrogateescape")
        if self.spaceUsed() + len(value) > self.capacity:
            return None, "not enough space"
        h.f.write(value)
        return True

    @method("Seeks in an open file descriptor. Returns the new position.")
    def seek(self, handle, whence, offset=0):
        h = self._handles.get(int(handle))
        if not h:
            return None, "bad file descriptor"
        wmap = {"set": 0, "cur": 1, "end": 2}
        if whence not in wmap:
            return None, "invalid mode"
        h.f.seek(int(offset), wmap[whence])
        return h.f.tell()

    def device_info(self):
        return {
            "class": "volume",
            "description": "Filesystem",
            "vendor": "MightyPirates GmbH & Co. KG",
            "product": "Spinpoint 4D" if not self.readonly else "Floppy",
            "capacity": str(self.capacity),
            "size": str(self.capacity),
        }

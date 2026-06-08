"""Internet card component.

Implements the HTTP ``request`` and TCP ``connect`` operations the OpenOS
``internet`` library expects. HTTP requests are performed with urllib; TCP
sockets use Python's socket module. Real network access is subject to the host
machine's network policy.
"""

from __future__ import annotations

import socket as pysocket
import urllib.request

from .base import Component, method


class HttpHandle:
    """Backing object for an in-flight HTTP request."""

    def __init__(self, url, post, headers, method_name, timeout=10):
        self.url = url
        self.post = post
        self.headers = headers or {}
        self.method_name = method_name
        self.timeout = timeout
        self._resp = None
        self._buf = b""
        self._eof = False
        self._error = None
        self._status = None
        self._message = ""
        self._resp_headers = {}

    def _ensure(self):
        if self._resp is not None or self._error is not None or self._eof:
            return
        try:
            data = self.post.encode("utf-8") if isinstance(self.post, str) else self.post
            req = urllib.request.Request(self.url, data=data, method=self.method_name)
            for k, v in self.headers.items():
                req.add_header(str(k), str(v))
            self._resp = urllib.request.urlopen(req, timeout=self.timeout)
            self._status = self._resp.getcode()
            self._message = getattr(self._resp, "reason", "") or ""
            self._resp_headers = {k: v for k, v in self._resp.headers.items()}
        except Exception as e:  # noqa: BLE001 - surface as OC error reason
            code = getattr(e, "code", None)
            if code is not None:
                # HTTP error responses still carry a readable body.
                self._status = code
                self._message = getattr(e, "reason", "") or ""
                try:
                    self._resp = e
                    self._resp_headers = {k: v for k, v in e.headers.items()}
                except Exception:
                    self._error = str(e)
            else:
                self._error = str(e)


class Internet(Component):
    ctype = "internet"

    def __init__(self, host, address=None):
        super().__init__(host, address)
        self.http_enabled = True
        self.tcp_enabled = True
        self._sockets = {}
        self._next_socket = 1

    @method("Returns whether HTTP requests can be made (config setting).")
    def isHttpEnabled(self):
        return self.http_enabled

    @method("Returns whether TCP connections can be made (config setting).")
    def isTcpEnabled(self):
        return self.tcp_enabled

    # -- HTTP ---------------------------------------------------------------

    @method("Sends an HTTP request. Returns a handle for the response.")
    def request(self, url, post=None, headers=None, method=None):
        if not self.http_enabled:
            return None, "http requests are unavailable"
        hdr = {}
        if headers is not None:
            try:
                hdr = {k: v for k, v in headers.items()}
            except Exception:
                hdr = {}
        m = method or ("POST" if post else "GET")
        backing = HttpHandle(url, post, hdr, m)

        lua = self.host.lua

        def read(n=None):
            backing._ensure()
            if backing._error:
                return None, backing._error
            if backing._buf:
                pass
            elif not backing._eof:
                try:
                    chunk = backing._resp.read(8192 if n is None else int(n))
                except Exception as e:
                    return None, str(e)
                if not chunk:
                    backing._eof = True
                    return None
                backing._buf = chunk
            else:
                return None
            if n is None:
                out, backing._buf = backing._buf, b""
            else:
                out, backing._buf = backing._buf[: int(n)], backing._buf[int(n):]
            return out

        def response():
            backing._ensure()
            if backing._status is None:
                return None
            return backing._status, backing._message, self.host.totable(backing._resp_headers)

        def finishConnect():
            backing._ensure()
            return backing._error is None

        def close():
            try:
                if backing._resp:
                    backing._resp.close()
            except Exception:
                pass
            return True

        handle = lua.table()
        handle["read"] = read
        handle["response"] = response
        handle["finishConnect"] = finishConnect
        handle["close"] = close
        return handle

    # -- TCP ----------------------------------------------------------------

    @method("Opens a TCP socket to the given address. Returns a handle.")
    def connect(self, address, port=None):
        if not self.tcp_enabled:
            return None, "tcp connections are unavailable"
        host = address
        if port is None and ":" in address:
            host, _, p = address.rpartition(":")
            port = int(p)
        try:
            sock = pysocket.create_connection((host, int(port)), timeout=10)
            sock.setblocking(False)
        except Exception as e:
            return None, str(e)

        lua = self.host.lua

        def read(n=None):
            try:
                data = sock.recv(int(n) if n else 8192)
                return data if data else None
            except BlockingIOError:
                return b""
            except Exception as e:
                return None, str(e)

        def write(value):
            if isinstance(value, str):
                value = value.encode("utf-8", "surrogateescape")
            try:
                return sock.send(value)
            except Exception as e:
                return None, str(e)

        def finishConnect():
            return True

        def close():
            try:
                sock.close()
            except Exception:
                pass
            return True

        handle = lua.table()
        handle["read"] = read
        handle["write"] = write
        handle["finishConnect"] = finishConnect
        handle["close"] = close
        return handle

    def device_info(self):
        return {
            "class": "communication",
            "description": "Internet modem",
            "vendor": "MightyPirates GmbH & Co. KG",
            "product": "HyperNet X4000",
        }

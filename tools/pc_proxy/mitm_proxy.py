#!/usr/bin/env python3
"""Local selective TLS MITM proxy for Google Antigravity (zero-modification bypass).

Listens on 127.0.0.1:18888 as an HTTP CONNECT proxy.
- Only Cloud Code endpoints (e.g. daily-cloudcode-pa.googleapis.com) are TLS-intercepted
  to normalize loadCodeAssist eligibility and clean incompatible consumer request fields.
- All other domains are relayed as raw transparent TCP tunnels without TLS interception.
"""

import gzip
import http.server
import json
import os
import select
import signal
import socket
import socketserver
import ssl
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 18888

PROXY_DIR = os.path.dirname(os.path.abspath(__file__))
LEAF_CERT = os.path.join(PROXY_DIR, "leaf.pem")
LEAF_KEY = os.path.join(PROXY_DIR, "leaf.key")
LOG_FILE = os.path.join(tempfile.gettempdir(), "antigravity_mitm_proxy.log")
MAX_LOG_BYTES = 5 * 1024 * 1024

MITM_HOSTS = {
    "daily-cloudcode-pa.googleapis.com",
    "cloudcode-pa.googleapis.com",
    "autopush-cloudcode-pa.googleapis.com",
    "staging-cloudcode-pa.googleapis.com",
}

# Ensure this process never loops upstream requests back to itself
for env_key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    val = os.environ.get(env_key, "")
    if str(PROXY_PORT) in val:
        os.environ.pop(env_key, None)

_log_lock = threading.Lock()


def log_debug(msg: str) -> None:
    try:
        with _log_lock:
            if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
                try:
                    os.replace(LOG_FILE, LOG_FILE + ".1")
                except OSError:
                    pass
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:12]}] {msg}\n")
    except Exception:
        pass


def _is_proxy_alive(host: str, port: int, timeout: float = 0.1) -> bool:
    """Quick probe to check if a local upstream proxy is actually accepting connections."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def get_upstream_http_proxy():
    """Return (host, port) of macOS system HTTPS/HTTP proxy if configured, not self, and alive."""
    try:
        proxies = urllib.request.getproxies()
        proxy_url = proxies.get("https") or proxies.get("http")
        if not proxy_url:
            return None
        parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
        if parsed.hostname and parsed.port:
            if parsed.hostname in ("127.0.0.1", "localhost", "::1"):
                if parsed.port == PROXY_PORT:
                    return None
                if not _is_proxy_alive(parsed.hostname, parsed.port):
                    return None
            return (parsed.hostname, parsed.port)
    except Exception:
        pass
    return None


def build_upstream_opener():
    """Build an opener reflecting current system proxy state (excluding self and dead local proxies)."""
    proxies = {}
    try:
        for proto, url in urllib.request.getproxies().items():
            if str(PROXY_PORT) in url:
                continue
            parsed = urlparse(url if "://" in url else f"http://{url}")
            if parsed.hostname in ("127.0.0.1", "localhost", "::1") and parsed.port:
                if not _is_proxy_alive(parsed.hostname, parsed.port):
                    continue
            proxies[proto] = url
    except Exception:
        pass
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))


def read_chunked_body(rfile) -> bytes:
    """Decode HTTP/1.1 Transfer-Encoding: chunked request body."""
    body = bytearray()
    while True:
        line = rfile.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            chunk_len = int(line.split(b";")[0], 16)
        except ValueError:
            break
        if chunk_len == 0:
            while True:
                trailer = rfile.readline()
                if not trailer or trailer.strip() == b"":
                    break
            break
        chunk = rfile.read(chunk_len)
        body.extend(chunk)
        rfile.readline()
    return bytes(body)


def connect_upstream_tcp(host: str, port: int) -> socket.socket:
    """Connect upstream via macOS system HTTP proxy (e.g. Shadowrocket) or directly via TUN/NIC."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        sys_proxy = get_upstream_http_proxy()
        if sys_proxy:
            p_host, p_port = sys_proxy
            try:
                sock = socket.create_connection((p_host, p_port), timeout=10)
                connect_req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode("ascii")
                sock.sendall(connect_req)
                buf = b""
                while b"\r\n\r\n" not in buf:
                    data = sock.recv(4096)
                    if not data:
                        raise ConnectionError("EOF from upstream proxy during CONNECT")
                    buf += data
                    if len(buf) > 16384:
                        raise ValueError("Header too large from upstream proxy")
                status_line = buf.split(b"\r\n", 1)[0]
                if b" 200 " in status_line:
                    sock.settimeout(None)
                    return sock
                sock.close()
            except Exception as e:
                log_debug(f"Upstream proxy {p_host}:{p_port} fallback to direct for {host}:{port}: {e}")

    sock = socket.create_connection((host, port), timeout=15)
    sock.settimeout(None)
    return sock


def relay_sockets(client_sock: socket.socket, remote_sock: socket.socket) -> None:
    """Bidirectional zero-copy-style TCP pipe using select."""
    sockets = [client_sock, remote_sock]
    try:
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets, 120)
            if exceptional:
                break
            if not readable:
                continue
            for s in readable:
                other = remote_sock if s is client_sock else client_sock
                try:
                    data = s.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                try:
                    other.sendall(data)
                except OSError:
                    return
    finally:
        for s in sockets:
            try:
                s.close()
            except Exception:
                pass


class MitmHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Handles decrypted HTTP/1.1 requests inside a MITM'd TLS connection."""

    protocol_version = "HTTP/1.1"
    disable_nagle_algorithm = True

    def __init__(self, request, client_address, server, target_host: str):
        self.target_host = target_host
        super().__init__(request, client_address, server)

    def setup(self):
        self.connection = self.request
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.rfile = self.connection.makefile("rb", self.rbufsize)
        self.wfile = self.connection.makefile("wb", self.wbufsize)

    def finish(self):
        try:
            super().finish()
        except Exception:
            pass

    def _read_request_body(self) -> bytes:
        te = self.headers.get("Transfer-Encoding", "").lower()
        if "chunked" in te:
            body = read_chunked_body(self.rfile)
        else:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b""

        if self.headers.get("Content-Encoding", "").lower() == "gzip" and body:
            try:
                body = gzip.decompress(body)
            except Exception:
                pass
        return body

    def _handle_request(self, method: str) -> None:
        try:
            body = self._read_request_body() if method in ("POST", "PUT", "PATCH") else None
            target_url = f"https://{self.target_host}{self.path}"

            headers = {}
            for k, v in self.headers.items():
                if k.lower() not in (
                    "host",
                    "content-length",
                    "accept-encoding",
                    "transfer-encoding",
                    "content-encoding",
                    "connection",
                    "proxy-connection",
                ):
                    headers[k] = v
            headers["Accept-Encoding"] = "identity"

            if body:
                try:
                    data = json.loads(body.decode("utf-8"))
                    changed = False
                    if "entitlement" in data:
                        del data["entitlement"]
                        changed = True
                    if data.get("project") in ("aicode-consumers", ""):
                        del data["project"]
                        changed = True
                    if changed:
                        body = json.dumps(data).encode("utf-8")
                except Exception:
                    pass

            if body is not None:
                log_debug(f"{method} {self.path} (len={len(body)})")
            else:
                log_debug(f"{method} {self.path}")

            req = urllib.request.Request(target_url, data=body, headers=headers, method=method)
            opener = build_upstream_opener()

            is_stream = "streamGenerateContent" in self.path or "alt=sse" in self.path
            try:
                try:
                    resp = opener.open(req, timeout=180)
                except urllib.error.HTTPError:
                    raise
                except Exception as opener_err:
                    log_debug(f"  Upstream opener error ({opener_err}), retrying direct...")
                    direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    direct_req = urllib.request.Request(target_url, data=body, headers=headers, method=method)
                    resp = direct_opener.open(direct_req, timeout=180)

                with resp:
                    if is_stream:
                        log_debug(f"  Streaming response start {resp.status}")
                        self.send_response(resp.status)
                        for k, v in resp.headers.items():
                            if k.lower() not in (
                                "content-length",
                                "content-encoding",
                                "transfer-encoding",
                                "connection",
                            ):
                                self.send_header(k, v)
                        self.send_header("Transfer-Encoding", "chunked")
                        self.end_headers()

                        total = 0
                        while True:
                            chunk = resp.read1(4096)
                            if not chunk:
                                break
                            total += len(chunk)
                            self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii") + chunk + b"\r\n")
                            self.wfile.flush()
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
                        log_debug(f"  Streaming response complete ({total} bytes)")
                        return

                    resp_data = resp.read()
                    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                        resp_data = gzip.decompress(resp_data)

                    if "loadCodeAssist" in self.path:
                        try:
                            res_json = json.loads(resp_data.decode("utf-8"))
                            res_json["ineligibleTiers"] = []
                            if "currentTier" in res_json and isinstance(res_json["currentTier"], dict):
                                res_json["currentTier"]["usesGcpTos"] = False
                                res_json["currentTier"]["userDefinedCloudaicompanionProject"] = False
                            for t in res_json.get("allowedTiers", []):
                                if isinstance(t, dict):
                                    t["usesGcpTos"] = False
                                    t["userDefinedCloudaicompanionProject"] = False
                            resp_data = json.dumps(res_json).encode("utf-8")
                            log_debug(f"  Patched loadCodeAssist response: {len(resp_data)} bytes")
                        except Exception as e:
                            log_debug(f"  Patch error: {e}")

                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        if k.lower() not in (
                            "content-length",
                            "content-encoding",
                            "transfer-encoding",
                            "connection",
                        ):
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(resp_data)))
                    self.end_headers()
                    self.wfile.write(resp_data)
                    self.wfile.flush()
                    log_debug(f"  Resp {resp.status} (len={len(resp_data)})")

            except urllib.error.HTTPError as e:
                err_data = e.read()
                if e.headers.get("Content-Encoding", "").lower() == "gzip":
                    try:
                        err_data = gzip.decompress(err_data)
                    except Exception:
                        pass

                log_debug(f"  HTTPError {e.code}: {err_data.decode('utf-8', errors='replace')[:400]}")

                if "onboardUser" in self.path:
                    resp_data = b"{}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp_data)))
                    self.end_headers()
                    self.wfile.write(resp_data)
                    self.wfile.flush()
                else:
                    self.send_response(e.code)
                    for k, v in e.headers.items():
                        if k.lower() not in (
                            "content-length",
                            "content-encoding",
                            "transfer-encoding",
                            "connection",
                        ):
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(err_data)))
                    self.end_headers()
                    self.wfile.write(err_data)
                    self.wfile.flush()

        except Exception as e:
            log_debug(f"  MITM exception on {method} {self.path}: {e}")
            err_msg = str(e).encode("utf-8")
            try:
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(err_msg)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(err_msg)
                self.wfile.flush()
            except Exception:
                pass
            self.close_connection = True

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def do_PUT(self):
        self._handle_request("PUT")

    def do_DELETE(self):
        self._handle_request("DELETE")

    def do_PATCH(self):
        self._handle_request("PATCH")

    def log_message(self, *args):
        pass


class OuterProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP CONNECT proxy router: selective TLS MITM vs transparent TCP tunnel."""

    protocol_version = "HTTP/1.1"
    disable_nagle_algorithm = True

    def do_CONNECT(self):
        host_port = self.path
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            host, port = host_port, 443
        host = host.strip("[]")

        if host in MITM_HOSTS:
            try:
                self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self.wfile.flush()
                tls_sock = self.server.ssl_ctx.wrap_socket(self.connection, server_side=True)
                MitmHTTPHandler(tls_sock, self.client_address, self.server, target_host=host)
            except ssl.SSLError as e:
                log_debug(f"TLS handshake error from client for {host}: {e}")
            except Exception as e:
                log_debug(f"MITM connection error for {host}: {e}")
            finally:
                self.close_connection = True
            return

        # Transparent raw TCP tunnel for all non-MITM hosts
        try:
            remote_sock = connect_upstream_tcp(host, port)
        except Exception as e:
            log_debug(f"CONNECT failed for {host}:{port}: {e}")
            try:
                self.send_error(502, f"Bad Gateway: {e}")
            except Exception:
                pass
            self.close_connection = True
            return

        try:
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            self.close_connection = True
            relay_sockets(self.connection, remote_sock)
        except Exception:
            try:
                remote_sock.close()
            except Exception:
                pass
            self.close_connection = True

    def log_message(self, *args):
        pass


class MitmProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass):
        self.ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ssl_ctx.load_cert_chain(certfile=LEAF_CERT, keyfile=LEAF_KEY)
        super().__init__(server_address, RequestHandlerClass)


def main():
    srv = MitmProxyServer((PROXY_HOST, PROXY_PORT), OuterProxyHandler)
    log_debug(f"Started Antigravity local MITM proxy on {PROXY_HOST}:{PROXY_PORT}")

    def shutdown_handler(signum, frame):
        log_debug("Shutting down MITM proxy...")
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    try:
        srv.serve_forever()
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()

"""Loopback-only HTTP adapter with same-origin, token and bounded-input guards."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
import json
import secrets
import socket
import webbrowser

from biocompiler.errors import BiocompilerError
from biocompiler.ir.serialization import parse_json
from biocompiler.studio import service
from biocompiler.studio import construction

MAX_BODY_BYTES = 2 * 1024 * 1024
_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/transport.js": ("transport.js", "text/javascript; charset=utf-8"),
    "/construction": ("construction.html", "text/html; charset=utf-8"),
    "/construction.css": ("construction.css", "text/css; charset=utf-8"),
    "/construction.js": ("construction.js", "text/javascript; charset=utf-8"),
}
_POST = {
    "/api/prepare": service.prepare,
    "/api/compile": service.compile_request,
    "/api/export": service.export,
    "/api/construction/inspect": construction.inspect,
    "/api/construction/save": construction.save,
}


class _RequestError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


class _Handler(BaseHTTPRequestHandler):
    server_version = "BiocompilerStudio"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # Avoid echoing untrusted request text or source contents to the terminal.
        pass

    def _respond(self, status, content, mime_type):
        self.send_response(status)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(content)

    def _json(self, status, document):
        content = json.dumps(
            document, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        self._respond(status, content, "application/json; charset=utf-8")

    def _error(self, status, code, message):
        self._json(status, {"ok": False, "error": {"code": code, "message": message}})

    def send_error(self, code, message=None, explain=None):
        self._error(
            code, "http_error", "The requested HTTP operation is not supported."
        )

    def _one_header(self, name):
        values = self.headers.get_all(name, [])
        if len(values) != 1:
            raise _RequestError(
                400, "invalid_headers", f"Exactly one {name} header is required."
            )
        return values[0]

    def _host(self):
        if self._one_header("Host") != self.server.studio_host:
            raise _RequestError(
                403, "invalid_host", "Use the exact loopback URL printed by Studio."
            )
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise _RequestError(
                403, "cross_origin", "Cross-site requests are not accepted."
            )

    def _post_body(self):
        if self._one_header("Origin") != self.server.studio_origin:
            raise _RequestError(
                403, "cross_origin", "A same-origin Studio request is required."
            )
        token = self._one_header("X-Biocompiler-Token")
        if not token.isascii() or not secrets.compare_digest(
            token, self.server.studio_token
        ):
            raise _RequestError(
                403, "invalid_token", "The Studio session token is missing or expired."
            )
        content_type = self._one_header("Content-Type").lower().replace(" ", "")
        if content_type not in ("application/json", "application/json;charset=utf-8"):
            raise _RequestError(415, "content_type", "Send UTF-8 application/json.")
        if self.headers.get_all("Transfer-Encoding"):
            raise _RequestError(
                400, "invalid_headers", "Chunked request bodies are not accepted."
            )
        length = self._one_header("Content-Length")
        if not length.isascii() or not length.isdecimal():
            raise _RequestError(
                400, "invalid_length", "Content-Length must be a nonnegative integer."
            )
        if len(length) > 10 or int(length) > MAX_BODY_BYTES:
            raise _RequestError(
                413,
                "body_too_large",
                f"Request bodies are limited to {MAX_BODY_BYTES} bytes.",
            )
        size = int(length)
        content = self.rfile.read(size)
        if len(content) != size:
            raise _RequestError(
                400, "incomplete_body", "The request body is incomplete."
            )
        try:
            document = parse_json(content.decode("utf-8"))
            service.bounded_document(document)
            return document
        except UnicodeError as exc:
            raise _RequestError(
                400, "invalid_json", "JSON must be valid UTF-8."
            ) from exc

    def _dispatch(self):
        try:
            self._host()
            if self.command in {"GET", "HEAD"}:
                if self.path == "/api/session" and self.command == "GET":
                    self._json(
                        200,
                        {
                            "ok": True,
                            "result": service.session(self.server.studio_token),
                        },
                    )
                    return
                if self.path in _STATIC:
                    filename, mime_type = _STATIC[self.path]
                    content = (
                        resources.files("biocompiler.studio")
                        .joinpath("static", filename)
                        .read_bytes()
                    )
                    self._respond(200, content, mime_type)
                    return
                raise _RequestError(
                    404, "not_found", "This Studio resource does not exist."
                )
            if self.path not in _POST:
                raise _RequestError(
                    404, "not_found", "This Studio API endpoint does not exist."
                )
            result = _POST[self.path](self._post_body())
            self._json(200, {"ok": True, "result": result})
        except _RequestError as exc:
            self._error(exc.status, exc.code, exc.message)
        except BiocompilerError as exc:
            self._error(400, "invalid_request", str(exc))
        except (TimeoutError, socket.timeout):
            self._error(408, "request_timeout", "The local request timed out.")
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            self._error(
                500,
                "internal_error",
                "The local compiler could not complete this request.",
            )

    do_GET = _dispatch
    do_HEAD = _dispatch
    do_POST = _dispatch


def create_server(port=8765):
    """Create a server bound only to IPv4 loopback; port zero is useful for tests."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Studio port must be an integer between 0 and 65535.")
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    server.daemon_threads = True
    server.studio_host = f"127.0.0.1:{server.server_port}"
    server.studio_origin = "http://" + server.studio_host
    server.studio_token = secrets.token_urlsafe(32)
    return server


def serve(port=8765, open_browser=False):
    server = create_server(port)
    print(f"Biocompiler Studio: {server.studio_origin}/", flush=True)
    try:
        if open_browser:
            webbrowser.open(server.studio_origin + "/")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

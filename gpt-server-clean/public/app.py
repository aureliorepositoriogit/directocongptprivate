#!/usr/bin/env python3
"""
A simple web server implementing a two‑chat interface that talks to the OpenAI
Chat API. The server hosts three pages:

  • /control    – administrative console for managing configuration and
                  monitoring all messages.  From this page you can
                  modify the ‘orden_prefijagpt’ instruction that is prepended
                  to every user input, and open the Decorador chat window.

  • /decorador  – chat interface for the "Decorador" role.  Messages sent
                  from here are prefaced with the configured orden and
                  forwarded to OpenAI.  Replies are broadcast to all pages.

  • /client     – chat interface for the "Cliente" role.  This page is
                  intended to be embedded in a Google Site via an iframe.

All pages poll the server every second for new messages.  This polling
scheme avoids the need for external websocket libraries and works with
standard browser APIs.  Messages and the fixed instruction are persisted
between restarts in a JSON file.

To run the server install nothing beyond the Python standard library.
Set the OPENAI_API_KEY environment variable before launching, e.g.:

    export OPENAI_API_KEY=sk‑yourkeyhere
    python3 app.py

You can then visit http://localhost:8000/control in a browser.  To embed
the client chat in Google Sites use an iframe pointing at
http://your‑server‑hostname/client.  Ensure your server is publicly
reachable from Google Sites when embedding.

Note: this code calls the OpenAI API at runtime.  The API key must not
be embedded in the client side; it is read only on the server side.
"""

import json
import os
import threading
import time
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import sys

try:
    import urllib.request as urllib_request
except ImportError:
    import urllib2 as urllib_request  # type: ignore


DATA_FILE = Path(__file__).parent / "data.json"

# In‑memory state loaded from and persisted to DATA_FILE.
state_lock = threading.Lock()
state = {
    "orden_prefijagpt": "",  # fixed instruction appended before user text
    "messages": [],           # list of message dicts: {timestamp, role, text, type}
}

#
# You can optionally configure your OpenAI API key directly in this file.
# By default the server reads the API key from the environment variable
# `OPENAI_API_KEY`.  If you prefer to hard‑code it here (not recommended
# for public deployments), set API_KEY below.  When API_KEY is non‑empty
# it takes precedence over the environment variable.  Do **not** commit
# your real key into version control!
API_KEY = "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"


def load_state() -> None:
    """Load state from the JSON persistence file if it exists."""
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf‑8"))
            with state_lock:
                state.update(data)
        except Exception:
            # Corrupt or unreadable file; start fresh
            pass


def save_state() -> None:
    """Write the current state to the JSON persistence file."""
    tmp_file = DATA_FILE.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf‑8") as f:
        json.dump(state, f)
    tmp_file.replace(DATA_FILE)


def call_openai(prompt: str) -> str:
    """Send a prompt to the OpenAI ChatCompletion API and return the response.

    This function requires the environment variable OPENAI_API_KEY to be
    defined.  It raises an exception if the request fails.  Responses are
    returned as plain text.
    """
    # Use the hard‑coded API_KEY if present; otherwise fall back to
    # environment variable.  This allows private, local deployments to
    # embed the key directly in code.  Avoid committing real keys!
    api_key = API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No OpenAI API key configured. Set API_KEY in app.py or "
            "define the OPENAI_API_KEY environment variable."
        )

    # Prepare the payload for the chat completion endpoint.  Use the
    # gpt‑3.5‑turbo model by default.  The prompt is sent as a user
    # message; if you need to specify a system role you can adjust
    # messages accordingly.  The state["orden_prefijagpt"] is always
    # prepended to the user text.
    payload = {
        "model": "gpt‑3.5‑turbo",
        "messages": [
            {"role": "system", "content": state["orden_prefijagpt"]},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    data = json.dumps(payload).encode("utf‑8")
    req = urllib_request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=data,
        headers={
            "Content‑Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            resp_data = resp.read()
    except Exception as e:
        raise RuntimeError(f"Error calling OpenAI API: {e}")
    try:
        resp_json = json.loads(resp_data.decode("utf‑8"))
        return resp_json["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"Malformed response from OpenAI: {e}")


class ChatHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the chat application."""

    # Directory containing our static assets.  Files in this directory
    # (and subdirectories) are served as‑is.  Avoid directory traversal by
    # resolving the requested path under this root.
    static_root = Path(__file__).parent / "public"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/messages"):
            self.handle_get_messages(parsed)
        elif path == "/config":
            self.handle_get_config()
        else:
            self.handle_get_static(path)

    def handle_get_messages(self, parsed) -> None:
        """Return messages newer than the provided timestamp."""
        params = parse_qs(parsed.query)
        after = 0.0
        if "after" in params:
            try:
                after = float(params["after"][0])
            except ValueError:
                pass
        with state_lock:
            new_msgs = [m for m in state["messages"] if m["timestamp"] > after]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content‑Type", "application/json; charset=utf‑8")
        self.end_headers()
        self.wfile.write(json.dumps(new_msgs).encode("utf‑8"))

    def handle_get_config(self) -> None:
        """Return the current configuration (orden_prefijagpt)."""
        with state_lock:
            config = {"orden_prefijagpt": state["orden_prefijagpt"]}
        self.send_response(HTTPStatus.OK)
        self.send_header("Content‑Type", "application/json; charset=utf‑8")
        self.end_headers()
        self.wfile.write(json.dumps(config).encode("utf‑8"))

    def handle_get_static(self, path: str) -> None:
        """Serve static files from the public directory."""
        # Default to control page when path is root
        if path == "/":
            rel_path = "control.html"
        else:
            rel_path = path.lstrip("/")
        fs_path = (self.static_root / rel_path).resolve()
        # Prevent directory traversal by ensuring the file lies under static_root
        try:
            fs_path.relative_to(self.static_root)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return
        if fs_path.is_dir():
            fs_path = fs_path / "index.html"
        if not fs_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        # Determine content type based on suffix
        ctype = "text/html"
        if fs_path.suffix == ".css":
            ctype = "text/css"
        elif fs_path.suffix == ".js":
            ctype = "application/javascript"
        elif fs_path.suffix in {".png", ".jpg", ".jpeg", ".gif"}:
            ctype = f"image/{fs_path.suffix.lstrip('.') }"
        try:
            data = fs_path.read_bytes()
        except Exception:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Error reading file")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content‑Type", ctype)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content‑Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        # Attempt to parse JSON body
        try:
            data = json.loads(body.decode("utf‑8")) if body else {}
        except Exception:
            data = {}
        if path == "/send_message":
            self.handle_send_message(data)
        elif path == "/update_order":
            self.handle_update_order(data)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def handle_send_message(self, data) -> None:
        """Process a user message: call OpenAI and broadcast response."""
        role = data.get("role") or "cliente"
        text = (data.get("message") or "").strip()
        if not text:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return
        timestamp = time.time()
        # Store the user's message
        with state_lock:
            state["messages"].append(
                {
                    "timestamp": timestamp,
                    "role": role,
                    "text": text,
                    "type": "user",
                }
            )
            save_state()
        # Call OpenAI synchronously
        try:
            response_text = call_openai(text)
        except Exception as e:
            response_text = f"Error: {e}"
        # Record assistant reply with timestamp slightly after user message
        reply_time = time.time()
        with state_lock:
            state["messages"].append(
                {
                    "timestamp": reply_time,
                    "role": "assistant",
                    "text": response_text,
                    "type": "assistant",
                }
            )
            save_state()
        # Return the assistant reply to the caller
        self.send_response(HTTPStatus.OK)
        self.send_header("Content‑Type", "application/json; charset=utf‑8")
        self.end_headers()
        self.wfile.write(json.dumps({"reply": response_text}).encode("utf‑8"))

    def handle_update_order(self, data) -> None:
        """Update the orden_prefijagpt instruction."""
        new_order = (data.get("orden_prefijagpt") or "").strip()
        with state_lock:
            state["orden_prefijagpt"] = new_order
            save_state()
        self.send_response(HTTPStatus.OK)
        self.end_headers()


def run(server_class=ThreadingHTTPServer, handler_class=ChatHandler, port: int = 8000) -> None:
    """Entrypoint: start the HTTP server on the specified port."""
    load_state()
    address = ("", port)
    httpd = server_class(address, handler_class)
    print(f"Serving on http://localhost:{port} … (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run(port=port)
"""Loopback contract for the real MediaWiki HTTP session."""

from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlsplit

from erenshor.infrastructure.wiki.client import MediaWikiClient
from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestPolicy


class _LoopbackHandler(BaseHTTPRequestHandler):
    """Serve deterministic API responses while recording wire requests."""

    protocol_version = "HTTP/1.0"
    requests: ClassVar[list[dict[str, Any]]] = []
    created: ClassVar[dict[str, str] | None] = None

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        params = parse_qs(parsed.query, keep_blank_values=True)
        self.requests.append(
            {
                "method": "GET",
                "path": parsed.path,
                "query": parsed.query,
                "params": params,
                "headers": dict(self.headers),
            }
        )
        if "revids" in params:
            assert self.created is not None
            payload = {
                "curtimestamp": "2026-06-04T12:00:02Z",
                "query": {
                    "pages": {
                        "2": {
                            "pageid": 2,
                            "title": self.created["title"],
                            "revisions": [
                                {
                                    "revid": 2,
                                    "parentid": 0,
                                    "timestamp": "2026-06-04T12:00:01Z",
                                    "user": "ContractBot",
                                    "slots": {"main": {"*": self.created["text"], "contentmodel": "wikitext"}},
                                }
                            ],
                        }
                    }
                },
            }
        elif "curtimestamp" in params:
            payload = {
                "curtimestamp": "2026-06-04T12:00:00Z",
                "query": {"pages": {"-1": {"title": params["titles"][0], "missing": ""}}},
            }
        else:
            payload = {
                "query": {
                    "pages": {
                        "1": {
                            "title": "Contract Page &/?",
                            "revisions": [{"slots": {"main": {"*": "existing text"}}}],
                        }
                    }
                }
            }
        self._respond(payload, cookie="session=contract-cookie; Path=/")

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode("utf-8")
        self.requests.append(
            {
                "method": "POST",
                "path": parsed.path,
                "query": parsed.query,
                "params": parse_qs(parsed.query, keep_blank_values=True),
                "form": parse_qs(body, keep_blank_values=True),
                "body": body,
                "headers": dict(self.headers),
            }
        )
        form = parse_qs(body, keep_blank_values=True)
        type(self).created = {"title": form["title"][0], "text": form["text"][0]}
        self._respond({"edit": {"result": "Success", "oldrevid": 0, "newrevid": 2}})

    def _respond(self, payload: dict[str, Any], *, cookie: str | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the contract output quiet."""


def test_mediawiki_client_preserves_loopback_session_encoding() -> None:
    """A real client encodes query/form data and carries GET cookies into POST."""
    _LoopbackHandler.requests = []
    _LoopbackHandler.created = None
    server = HTTPServer(("127.0.0.1", 0), _LoopbackHandler)
    thread: threading.Thread | None = None

    title = "Contract Page &/?"
    new_title = "New Contract Page &/?"
    try:
        thread = threading.Thread(target=server.serve_forever, name="mediawiki-loopback", daemon=True)
        thread.start()
        api_url = f"http://127.0.0.1:{server.server_port}/api.php"
        with MediaWikiClient(
            api_url=api_url,
            bot_username="ContractBot",
            timeout=3.0,
            request_policy=MediaWikiRequestPolicy(max_retries=0, jitter=0),
        ) as client:
            assert client.get_page(title) == "existing text"
            # The cached token leaves one mutation POST between native base and receipt reads.
            # Token acquisition is separately covered by unit tests.
            client._csrf_token = "csrf-token+/="
            client.safe_create_page(
                new_title,
                "updated text & = / + %",
                start_timestamp="2026-06-04T12:00:00Z",
                summary="summary & details",
                minor=False,
                bot=False,
                assertion="user",
            )

        requests = _LoopbackHandler.requests
        assert [request["method"] for request in requests] == ["GET", "GET", "POST", "GET"]
        get_request, preflight, post_request, receipt = requests
        assert preflight["params"]["titles"] == [new_title]
        assert preflight["params"]["curtimestamp"] == ["1"]
        assert receipt["params"]["revids"] == ["2"]
        assert get_request["path"] == "/api.php"
        assert get_request["params"] == {
            "action": ["query"],
            "titles": [title],
            "prop": ["revisions"],
            "rvprop": ["content"],
            "rvslots": ["main"],
            "format": ["json"],
            "maxlag": ["5"],
        }
        assert "titles=Contract+Page+%26%2F%3F" in get_request["query"]

        assert post_request["path"] == "/api.php"
        assert post_request["params"] == {"format": ["json"], "maxlag": ["5"]}
        assert post_request["form"] == {
            "action": ["edit"],
            "title": [new_title],
            "text": ["updated text & = / + %"],
            "summary": ["summary & details"],
            "createonly": ["1"],
            "starttimestamp": ["2026-06-04T12:00:00Z"],
            "md5": [hashlib.md5(b"updated text & = / + %", usedforsecurity=False).hexdigest()],
            "assert": ["user"],
            "token": ["csrf-token+/="],
        }
        assert "text=updated+text+%26+%3D+%2F+%2B+%25" in post_request["body"]
        assert get_request["headers"]["User-Agent"] == "ContractBot/0.3 (automated wiki updates) httpx"
        assert post_request["headers"]["User-Agent"] == "ContractBot/0.3 (automated wiki updates) httpx"
        assert post_request["headers"]["Cookie"] == "session=contract-cookie"
    finally:
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            assert not thread.is_alive()

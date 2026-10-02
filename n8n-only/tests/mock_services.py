"""Fake OpenAI, Cloudinary and Instagram Graph API used only for testing.

Nothing here talks to the real services. Run:  python3 mock_services.py 9999
"""

from __future__ import annotations

import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# 1x1 PNG
PNG = base64.b64encode(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000002000154a24f5b0000000049454e44ae426082")).decode()
LOCK = threading.Lock()
STATE = {"containers": {}, "published": [], "requests": [], "saved": []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        if "json" in (self.headers.get("Content-Type") or ""):
            return json.loads(raw or "{}")
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        with LOCK:
            STATE["requests"].append({"method": "GET", "path": u.path, "query": q})
        if u.path == "/state":
            return self._send(200, STATE)
        if q.get("access_token") != "test-token":
            return self._send(400, {"error": {"message": "Invalid OAuth access token", "type": "OAuthException", "code": 190}})
        obj = u.path.rsplit("/", 1)[-1]
        if q.get("fields") == "status_code":
            if obj not in STATE["containers"]:
                return self._send(400, {"error": {"message": "Unsupported get request", "code": 100}})
            return self._send(200, {"id": obj, "status_code": "FINISHED"})
        if q.get("fields") == "permalink":
            return self._send(200, {"id": obj, "permalink": f"https://www.instagram.com/p/MOCK{obj}/"})
        return self._send(404, {"error": {"message": "unknown"}})

    def do_POST(self):
        u = urlparse(self.path)
        body = self._body()
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        with LOCK:
            STATE["requests"].append({"method": "POST", "path": u.path, "query": q, "body": {k: (v if len(str(v)) < 300 else str(v)[:60] + "...") for k, v in body.items()}})
        # ---- OpenAI ----
        if u.path.endswith("/chat/completions"):
            if self.headers.get("Authorization") != "Bearer test-openai-key":
                return self._send(401, {"error": {"message": "Incorrect API key provided"}})
            user = body["messages"][1]["content"]
            if "FAILME" in user:
                return self._send(500, {"error": {"message": "The server had an error while processing your request"}})
            topic = user.split("- Topic: ", 1)[1].split("\n", 1)[0]
            post = {
                "headline": f"{topic} made simple",
                "caption": f"Struggling with {topic.lower()}? Here are 3 quick tips.\n\nJoin our crash course for just ₹4,999!\nExam on [EXAM DATE].\n\nFollow us for more.",
                "hashtags": ["#examtips", "students", "study tips", "examtips"],
                "image_prompt": f"Bright illustration of students preparing for {topic}",
                "missing_information": ["Exact exam date"],
            }
            return self._send(200, {"choices": [{"message": {"role": "assistant", "content": json.dumps(post)}}], "model": body.get("model")})
        if u.path.endswith("/images/generations"):
            return self._send(200, {"data": [{"b64_json": PNG}]})
        # ---- Cloudinary ----
        if u.path.endswith("/image/upload"):
            if not body.get("upload_preset") or not str(body.get("file", "")).startswith("data:image/png;base64,") or len(body["file"]) < 40:
                return self._send(400, {"error": {"message": "Invalid file or upload preset"}})
            return self._send(200, {"secure_url": "https://res.cloudinary.com/demo/image/upload/v1/instagram-automation/abc123.png"})
        # ---- Test-only: records what workflow 3 would save to the sheet ----
        if u.path == "/saved":
            with LOCK:
                STATE["saved"].extend(body.get("rows", []))
            return self._send(200, {"ok": True})
        # ---- Instagram Graph API ----
        if q.get("access_token") != "test-token":
            return self._send(400, {"error": {"message": "Invalid OAuth access token", "type": "OAuthException", "code": 190}})
        if u.path.endswith("/media"):
            if "TOKENFAIL" in body.get("caption", ""):
                return self._send(400, {"error": {"message": "Error validating access token", "type": "OAuthException", "code": 190}})
            if not body.get("image_url", "").startswith("https://"):
                return self._send(400, {"error": {"message": "Invalid image URL", "code": 100}})
            with LOCK:
                cid = str(17900000000 + len(STATE["containers"]) + 1)
                STATE["containers"][cid] = body
            return self._send(200, {"id": cid})
        if u.path.endswith("/media_publish"):
            cid = body.get("creation_id")
            if cid not in STATE["containers"]:
                return self._send(400, {"error": {"message": "Media ID is not available", "code": 9007}})
            with LOCK:
                if cid in [p["container"] for p in STATE["published"]]:
                    return self._send(400, {"error": {"message": "already published", "code": 9004}})
                mid = str(18000000000 + len(STATE["published"]) + 1)
                STATE["published"].append({"container": cid, "media": mid})
            return self._send(200, {"id": mid})
        return self._send(404, {"error": {"message": "unknown endpoint " + u.path}})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

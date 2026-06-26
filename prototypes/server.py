#!/usr/bin/env python3
import json
import os
import re
import hashlib
import sys
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.items = []
        self._tag_stack = []
        self._current = None
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        self._tag_stack.append(tag)
        if tag in {"title", "h1", "h2", "h3", "p", "li", "td", "th"}:
            self._current = {"tag": tag, "text": ""}

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._current and self._current["tag"] == tag:
            text = normalize_text(self._current["text"])
            if text:
                if tag == "title" and not self.title:
                    self.title = text
                elif len(text) > 18:
                    self.items.append({"tag": tag, "text": text})
            self._current = None
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data):
        if self._skip_depth or not self._current:
            return
        self._current["text"] += data + " "


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def fetch_readable(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http(s) URLs are supported")

    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 IZANOFFER prototype reader",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(req, timeout=15) as res:
        content_type = res.headers.get("Content-Type", "")
        if "html" not in content_type:
            raise ValueError(f"URL did not return HTML: {content_type}")
        html = res.read(1_500_000).decode("utf-8", errors="replace")

    parser = ReadableHTMLParser()
    parser.feed(html)

    seen = set()
    blocks = []
    for item in parser.items:
        text = item["text"]
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        blocks.append(item)
        if len(blocks) >= 60:
            break

    return {
        "url": url,
        "host": parsed.netloc,
        "path": parsed.path or "/",
        "title": parser.title or parsed.netloc,
        "blocks": blocks,
    }


def users_path():
    return Path(__file__).with_name("users.json")


def load_users():
    path = users_path()
    if not path.exists():
        return {"users": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_users(data):
    users_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def public_user(user):
    return {
        "email": user["email"],
        "role": user.get("role", "user"),
        "profile": user.get("profile", {}),
        "profileComplete": bool(user.get("profileComplete")),
    }


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/config":
            self.send_json(200, {
                "clerkPublishableKey": os.environ.get("CLERK_PUBLISHABLE_KEY", ""),
                "mockAuth": True,
                "adminEmail": "451248901@qq.com"
            })
            return
        if self.path == "/api/trending":
            data_path = Path(__file__).with_name("trending.json")
            if data_path.exists():
                self.send_json(200, json.loads(data_path.read_text(encoding="utf-8")))
            else:
                self.send_json(200, {"questions": [], "links": []})
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/extract":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                payload = json.loads(body.decode("utf-8"))
                data = fetch_readable(payload.get("url", ""))
                self.send_json(200, data)
            except Exception as exc:
                self.send_json(400, {"error": str(exc)})
            return

        if self.path in {"/api/mock-auth/login", "/api/mock-auth/register", "/api/mock-auth/profile"}:
            self.handle_mock_auth()
            return

        self.send_error(404)

    def read_payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def handle_mock_auth(self):
        try:
            payload = self.read_payload()
            data = load_users()
            users = data.setdefault("users", [])
            email = normalize_text(payload.get("email", "")).lower()

            if self.path == "/api/mock-auth/register":
                if not email or "@" not in email:
                    raise ValueError("请输入有效邮箱")
                if len(payload.get("password", "")) < 6:
                    raise ValueError("密码至少 6 位")
                if any(u["email"] == email for u in users):
                    raise ValueError("这个邮箱已注册，请直接登录")
                user = {
                    "email": email,
                    "passwordHash": password_hash(payload["password"]),
                    "role": "admin" if email == "451248901@qq.com" else "user",
                    "profile": {},
                    "profileComplete": False,
                }
                users.append(user)
                save_users(data)
                self.send_json(200, {"user": public_user(user)})
                return

            user = next((u for u in users if u["email"] == email), None)
            if not user:
                raise ValueError("账号不存在，请先注册")

            if self.path == "/api/mock-auth/login":
                if user["passwordHash"] != password_hash(payload.get("password", "")):
                    raise ValueError("密码不正确")
                self.send_json(200, {"user": public_user(user)})
                return

            if self.path == "/api/mock-auth/profile":
                user["profile"] = payload.get("profile", {})
                user["profileComplete"] = True
                save_users(data)
                self.send_json(200, {"user": public_user(user)})
                return
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def send_json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving IZANOFFER prototype on http://127.0.0.1:{port}/C3-prototype.html")
    server.serve_forever()

"""The smoke test after a deploy (Staging readiness plan P10, ADR-071): the public entry answers, is hardened, hides
the API, and (with a login) a real sign-in reads `/me` and one finance week. Standard library only (runs on the
deployment host with `python3`, in the CI and on the owner's machine).

Commands (from the project root):
    python pipelines/scripts/ops/Deploy_smoke.py --origin https://staging.example.com
    python pipelines/scripts/ops/Deploy_smoke.py --origin https://localhost:8443 --ca-file <caddy root.crt>
        [--stack portpilot-rehearsal]      also checks inside the stack: the API's /health/status, the scheduler's plan
        [--email someone@nilegate.com]     also signs in (password from SMOKE_PASSWORD, never an argument), reads /me
                                           and /finance/weeks, signs out
Exit 0 = every check passed; 1 = a check failed (its name printed). Prints no secret.
Reads:   the public site; with --stack, `docker exec` into <stack>-api / <stack>-scheduler. Writes: nothing (a sign-in
         writes the API's own audit rows; the token is revoked at the end).
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


class Client:
    def __init__(self, origin: str, ca_file: str | None):
        self.origin = origin.rstrip("/")
        ctx = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                                  urllib.request.HTTPCookieProcessor(self.jar),
                                                  NoRedirect())

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"accept": "application/json, text/html", **(headers or {})}
        if data is not None:
            h["content-type"] = "application/json"
        req = urllib.request.Request(self.origin + path, data=data, method=method, headers=h)
        try:
            with self.opener.open(req, timeout=20) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def cookie(self, name: str) -> str | None:
        return next((c.value for c in self.jar if c.name == name), None)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 — keep 3xx visible
        return None


def lower(h: dict) -> dict:
    return {k.lower(): v for k, v in h.items()}


def public(c: Client) -> None:
    deadline = time.time() + 120
    status, body = 0, b""
    while time.time() < deadline:                      # the stack may still be starting
        try:
            status, _h, body = c.request("GET", "/healthz")
            if status == 200:
                break
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(3)
    check("GET /healthz = 200 ok (web up, API ready)", status == 200 and json.loads(body or b"{}").get("status") == "ok",
          f"{status} {body[:120]!r}")
    status, h, body = c.request("GET", "/login")
    h = lower(h)
    check("GET /login = 200 HTML", status == 200 and "text/html" in h.get("content-type", ""), str(status))
    csp = h.get("content-security-policy", "")
    check("CSP with a nonce, frame-ancestors none", "'nonce-" in csp and "frame-ancestors 'none'" in csp, csp[:120])
    check("HSTS set by the proxy", "max-age=" in h.get("strict-transport-security", ""))
    check("X-Frame-Options DENY, nosniff", h.get("x-frame-options") == "DENY"
          and h.get("x-content-type-options") == "nosniff")
    check("no Server / X-Powered-By header", "server" not in h and "x-powered-by" not in h,
          f"{h.get('server')} {h.get('x-powered-by')}")
    for path in ("/api/v1/health/live", "/docs", "/openapi.json"):
        status, _h, _b = c.request("GET", path)
        check(f"the API is not public: GET {path} = 404", status == 404, str(status))
    status, _h, _b = c.request("POST", "/bff/login", {"email": "nobody@example.com", "password": "x"},
                               {"origin": "https://evil.example"})
    check("sign-in from another origin = 403", status == 403, str(status))


def plain_http(http_origin: str) -> None:
    try:
        status, h, _b = Client(http_origin, None).request("GET", "/login")
        check("plain http redirects to https", status in (301, 302, 307, 308)
              and lower(h).get("location", "").startswith("https://"), f"{status} {lower(h).get('location')}")
    except (urllib.error.URLError, OSError) as exc:
        check("plain http closed (nothing served without TLS)", True, type(exc).__name__)


def signed_in(c: Client, email: str, password: str) -> None:
    status, _h, body = c.request("POST", "/bff/login", {"email": email, "password": password}, {"origin": c.origin})
    check("sign-in = 200 and the session cookie set", status == 200 and c.cookie("ng_session") is not None, str(status))
    if status != 200:
        return
    me = json.loads(body).get("me", {})
    check("/me names a role", bool(me.get("role")), str(list(me)[:5]))
    csrf = c.cookie("ng_csrf") or ""                   # web/src/lib/bff/names.ts
    status, _h, body = c.request("GET", "/bff/me")                     # the BFF drops the API's /api/v1 prefix
    check("GET /bff/me = 200", status == 200, str(status))
    status, _h, body = c.request("GET", "/bff/finance/weeks")
    check("GET /bff/finance/weeks = 200 or 403 (by role)", status in (200, 403), str(status))
    status, _h, _b = c.request("POST", "/bff/logout", {}, {"origin": c.origin, "x-csrf-token": csrf})
    check("sign-out = 2xx", 200 <= status < 300, str(status))


def inside(stack: str) -> None:
    code = ("import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/status',"
            "timeout=10); print(json.load(r)['status'])")
    r = subprocess.run(["docker", "exec", f"{stack}-api", "python", "-c", code], capture_output=True, text=True)
    check("inside: the API's /health/status = ready", r.stdout.strip() == "ready", (r.stdout + r.stderr)[-200:])
    r = subprocess.run(["docker", "exec", f"{stack}-scheduler", "python", "pipelines/scripts/ops/Scheduler_service.py",
                        "--plan"], capture_output=True, text=True)
    check("inside: the scheduler knows both jobs", "weekly_pack" in r.stdout and "voyage_watch" in r.stdout,
          r.stderr[-200:])
    r = subprocess.run(["docker", "exec", f"{stack}-api", "python", "-c",
                        "import os; print(os.environ.get('PORTPILOT_ENV'), os.environ.get('API_FAKE_ROLES'))"],
                       capture_output=True, text=True)
    env_name, fake = (r.stdout.split() + ["", ""])[:2]
    check("inside: PORTPILOT_ENV is staging / production, no fake roles",
          env_name in ("staging", "production") and fake in ("None", ""), r.stdout.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--origin", required=True)
    ap.add_argument("--ca-file")
    ap.add_argument("--stack")
    ap.add_argument("--email")
    ap.add_argument("--http-origin", help="the plain-http address of the same site (default: http://<host>)")
    a = ap.parse_args()
    c = Client(a.origin, a.ca_file)
    public(c)
    host = a.origin.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    plain_http(a.http_origin or f"http://{host}")
    if a.stack:
        inside(a.stack)
    if a.email:
        password = os.environ.get("SMOKE_PASSWORD", "")
        if not password:
            check("SMOKE_PASSWORD set for --email", False)
        else:
            signed_in(c, a.email, password)
    print(f"{'✅ smoke passed' if not FAILED else f'❌ smoke failed: {len(FAILED)} check(s)'}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()

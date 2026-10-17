"""Verify same-origin hosted demo auth, CSRF, isolation, workflows and logout."""

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

base = sys.argv[1].rstrip("/")
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
csrf = ""


def call(path, body=None, method=None, expected=200):
    headers = {"Origin": base}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base + "/api" + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers=headers,
    )
    try:
        with client.open(request, timeout=45) as response:
            code, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        code, payload = error.code, error.read()
    if code != expected:
        raise SystemExit(
            f"Smoke check failed at {path}: HTTP {code}; response body withheld."
        )
    return json.loads(payload)


health = call("/health")
assert health["storage"] == "firestore" and health["demo_enabled"]
call("/overview", expected=401)
result = call(
    "/auth/login", {"email": "customer@aegis.demo", "password": "AegisDemo!2026"}
)
csrf = result["csrf_token"]
assert any(cookie.name == "__session" and cookie.secure for cookie in jar)
assert call("/auth/me")["user"]["role"] == "customer"
assert call("/overview")["account"]["currency"] == "INR"
assert {item["kind"] for item in call("/automations")["catalog"]} == {
    "financial_health", "security_review", "document_review", "savings_coach",
    "cashflow_review", "expense_review",
}
assert len(call("/knowledge")) == 6
assert len(call("/analysis")["cashflow"]["projections"]) == 3
assert call("/documents/guide-neft/content")["document"]["kind"] == "banking_guide"
call("/analyst/operations", expected=403)
call("/auth/logout", {}, method="POST")
call("/auth/me", expected=401)
print(
    "Hosted demo smoke checks passed: Firestore, secure session, authenticated APIs, workflow catalog, role isolation, logout."
)

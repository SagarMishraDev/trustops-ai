"""Post-deploy smoke test - run against ANY running TrustOps instance.

    BASE_URL=http://127.0.0.1:8000 python scripts/smoke_test.py

Checks the whole golden path with real HTTP calls: health -> business
creation -> demo seed -> analytics -> SIGNED webhook -> benchmark run.
Exits non-zero if any step fails, so it can gate a deployment pipeline.
Only stdlib is used - no project imports, it tests the deployed surface.
"""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
failures = []


def call(method, path, body=None, headers=None, raw_body=None):
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, method=method, data=data,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({extra})" if extra else ""))
    if not ok:
        failures.append(name)


def main():
    s, r = call("GET", "/health")
    check("health endpoint", s == 200 and r.get("status") == "ok")

    s, biz = call("POST", "/api/v1/businesses", {"name": "Smoke Test Biz"})
    check("business creation", s == 201 and biz.get("api_key", "").startswith("tok_")
          and biz.get("webhook_secret", "").startswith("whsec_"))
    if failures:
        return _finish()
    key, secret = biz["api_key"], biz["webhook_secret"]
    auth = {"X-API-Key": key}

    s, seed = call("POST", "/api/v1/demo/seed", {}, auth)
    check("demo seed", s == 200 and seed.get("evaluated", 0) >= 1, f"evaluated={seed.get('evaluated')}")

    s, ov = call("GET", "/api/v1/analytics/overview", headers=auth)
    check("analytics overview", s == 200 and ov.get("total_conversations", 0) >= 8,
          f"conversations={ov.get('total_conversations')} avg={ov.get('average_score')}")

    payload = {"conversation_id": "SMOKE-1", "user_message": "Where is my order?",
               "assistant_response": "Your order is delivered.",
               "timestamp": "2026-11-04T10:30:00", "session_id": "SM1"}
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    s, wh = call("POST", "/api/v1/webhooks/conversations", raw_body=body,
                 headers={**auth, "X-TrustOps-Timestamp": ts, "X-TrustOps-Signature": sig})
    check("signed webhook", s == 200 and wh.get("status") == "stored")

    s, err = call("POST", "/api/v1/webhooks/conversations", payload, auth)
    check("unsigned webhook rejected", s == 401 and err.get("error_code") == "missing_signature")

    s, run = call("POST", "/api/v1/benchmarks/run", {}, auth)
    check("benchmark run", s == 201 and run.get("total_cases") == 50, f"F1={run.get('f1_score')}")
    return _finish()


def _finish():
    if failures:
        print(f"\nSMOKE TEST FAILED: {len(failures)} step(s): {failures}")
        return 1
    print("\nSMOKE TEST PASSED: all steps green against " + BASE)
    return 0


if __name__ == "__main__":
    sys.exit(main())

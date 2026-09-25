#!/usr/bin/env python3
"""E2E: OTP login flow against the running dev backend."""
import json
import urllib.request

def gql(query, variables=None, token=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    req = urllib.request.Request(
        "http://localhost:8000/graphql",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# 1. request OTP for seeded customer
res = gql('mutation($p: String!) { requestOtp(phone: $p, purpose: "LOGIN") { sent devCode } }',
          {"p": "+2348012345001"})
payload = res["data"]["requestOtp"]
print("requestOtp sent:", payload["sent"], "| devCode present:", bool(payload["devCode"]))
assert payload["sent"] and payload["devCode"], payload

# 2. login with the code
res = gql(
    "mutation($p: String!, $c: String!) { loginWithOtp(phone: $p, code: $c)"
    " { accessToken refreshToken expiresInMinutes user { id phone firstName lastName } } }",
    {"p": "+2348012345001", "c": payload["devCode"]},
)
pair = res["data"]["loginWithOtp"]
print("loginWithOtp OK: user =", pair["user"]["firstName"], pair["user"]["phone"])
assert pair["accessToken"] and pair["refreshToken"]

# 3. the code must be one-time
res2 = gql(
    "mutation($p: String!, $c: String!) { loginWithOtp(phone: $p, code: $c) { accessToken } }",
    {"p": "+2348012345001", "c": payload["devCode"]},
)
print("replay blocked:", bool(res2.get("errors")))
assert res2.get("errors"), "OTP replay must fail"

# 4. authenticated call with OTP-issued token
res = gql("{ me { customerReference fullName } }", token=pair["accessToken"])
print("me via OTP token:", res["data"]["me"]["customerReference"])
assert res["data"]["me"]["customerReference"].startswith("RF-CUS-")

print("OTP_E2E_ALL_OK")

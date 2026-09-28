#!/usr/bin/env python3
"""FULL LIFECYCLE E2E with a FRESH registered test account.

Proves the complete workflow the deployment was asked to demonstrate:
  1. registerCustomer (brand new account) -> auto-login token
  2. Create a savings plan (SAVE_FLEX)
  3. makePayment (Paystack path) -> clean PROVIDER_ERROR while keys pending
  4. KYC: submit -> officer sees queue -> review APPROVED -> VERIFIED
  5. applyForLoan (TRADER) -> application PENDING
  6. Agent cash collection credits the new customer's plan
  7. Paystack webhook rejects unsigned payloads (401, quarantined)
"""
import json
import sys
import time
import urllib.request
import urllib.error

API = "https://testapi.inyene.com/graphql"
WEBHOOK = "https://testapi.inyene.com/payments/webhooks/paystack"

PASS = FAIL = 0


def post(url, body, token=None, extra_headers=None):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json",
               "User-Agent": "Mozilla/5.0 RFUND-E2E/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def gql(query, token=None, variables=None):
    _, body = post(API, {"query": query, "variables": variables or {}}, token)
    return body


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def main():
    phone = f"+23480123{int(time.time()) % 100000:05d}"
    print(f"== FULL LIFECYCLE E2E — fresh account {phone} ==")

    print("[1] Registration + login")
    reg = gql(
        "mutation($i: RegisterInput!) { registerCustomer(input: $i) { accessToken user { phone roles } } }",
        variables={"i": {"phone": phone, "password": "Test#2026",
                          "firstName": "E2E", "lastName": "Verified"}},
    )
    tok = (reg.get("data") or {}).get("registerCustomer", {}).get("accessToken")
    check("registerCustomer returns token", bool(tok), json.dumps(reg)[:300])

    log = gql(
        "mutation($i: LoginInput!) { login(input: $i) { accessToken user { phone roles } } }",
        variables={"i": {"phone": phone, "password": "Test#2026"}},
    )
    tok = (log.get("data") or {}).get("login", {}).get("accessToken")
    check("fresh account can login", bool(tok), json.dumps(log)[:300])

    print("[2] Savings plan creation")
    from datetime import date, timedelta
    start = date.today().isoformat()
    end = (date.today() + timedelta(days=90)).isoformat()
    plan_m = gql(
        "mutation($i: CreateSavingsPlanInput!) { createSavingsPlan(input: $i) { id reference productCode status } }",
        tok, {"i": {"productCode": "SAVE_FLEX", "amount": "5000",
                     "frequency": "MONTHLY", "startDate": start, "endDate": end}},
    )
    plan = (plan_m.get("data") or {}).get("createSavingsPlan") or {}
    check("createSavingsPlan SAVE_FLEX", bool(plan.get("reference")), json.dumps(plan_m)[:300])
    if plan:
        print(f"        plan {plan['reference']} ({plan['productCode']}) status={plan['status']}")

    print("[3] Paystack-wired deposit (keys pending -> clean provider error)")
    pay = gql(
        """mutation($i: MakePaymentInput!) { makePayment(input: $i) {
             payment { reference status provider } authorizationUrl } }""",
        tok, {"i": {"purpose": "SAVINGS_CONTRIBUTION", "amount": "2000",
                     "targetPlanId": plan.get("id"), "idempotencyKey": f"e2e-{int(time.time())}"}},
    )
    errs = pay.get("errors") or []
    prov_err = any(e.get("extensions", {}).get("code") == "PROVIDER_ERROR" for e in errs)
    ok_url = (pay.get("data") or {}).get("makePayment", {}).get("authorizationUrl")
    check("makePayment returns clean PROVIDER_ERROR or url",
          prov_err or bool(ok_url), json.dumps(pay)[:300])
    if prov_err:
        print(f"        message: {errs[0]['message'][:90]}")

    print("[4] KYC full cycle")
    sub = gql(
        "mutation($i: SubmitKYCInput!) { submitKyc(input: $i) { status level failureReason } }",
        tok, {"i": {"docType": "NIN", "idNumber": f"99{int(time.time()) % 10**9:09d}"}},
    )
    sd = (sub.get("data") or {}).get("submitKyc") or {}
    check("submitKyc accepted", sd.get("status") in {"PENDING", "IN_REVIEW", "SUBMITTED"},
          json.dumps(sub)[:300])

    kyc_tok = gql(
        "mutation($i: LoginInput!) { login(input: $i) { accessToken } }",
        variables={"i": {"phone": "+2348000000002", "password": "Kyc#2026"}},
    )["data"]["login"]["accessToken"]
    queue = gql(
        "query { adminKycQueue(first: 50) { items { id customerName status submittedDocType } } }",
        kyc_tok,
    )
    items = (queue.get("data") or {}).get("adminKycQueue", {}).get("items", [])
    profile = next((p for p in items if "E2E" in (p.get("customerName") or "")), None)
    check("officer sees E2E profile pending", profile is not None, json.dumps(queue)[:300])

    rev = gql(
        "mutation($i: ReviewKycInput!) { reviewKyc(input: $i) }",
        kyc_tok, {"i": {"profileId": profile["id"], "decision": "APPROVED",
                         "reason": "Full-cycle E2E", "newLevel": "STANDARD"}},
    )
    check("reviewKyc APPROVED", (rev.get("data") or {}).get("reviewKyc") is True,
          json.dumps(rev)[:300])

    st = gql("query { kycStatus { status level verifiedAt } }", tok)
    kd = st.get("data", {}).get("kycStatus", {})
    check("fresh account VERIFIED / STANDARD",
          kd.get("status") in {"VERIFIED", "APPROVED"} and kd.get("level") == "STANDARD",
          json.dumps(st)[:200])

    print("[5] Loan application (TRADER)")
    loan = gql(
        "mutation($i: ApplyForLoanInput!) { applyForLoan(input: $i) { id reference amountRequested state productCode productName } }",
        tok, {"i": {"productCode": "TRADER", "amount": "25000",
                     "termMonths": 6, "purpose": "E2E full-cycle",
                     "monthlyIncome": "120000"}},
    )
    ld = (loan.get("data") or {}).get("applyForLoan") or {}
    check("applyForLoan submitted", bool(ld.get("reference")), json.dumps(loan)[:300])
    if ld:
        print(f"        loan {ld['reference']} ₦{ld['amountRequested']} state={ld['state']} product={ld['productName']}")

    print("[6] Agent collection credits fresh account's plan")
    agent_tok = gql(
        "mutation($i: LoginInput!) { login(input: $i) { accessToken } }",
        variables={"i": {"phone": "+2348000000100", "password": "Agent#2026"}},
    )["data"]["login"]["accessToken"]
    custs = gql(
        "query { agentCustomers(first: 50) { items { id phone fullName kycTier status } } }",
        agent_tok,
    )
    target = next((c for c in custs["data"]["agentCustomers"]["items"]
                   if c["phone"] == phone), None)
    check("agent sees fresh customer in territory", target is not None,
          json.dumps(custs)[:200])
    if target and plan:
        coll = gql(
            """mutation($i: AgentCashCollectionInput!) {
                 agentCashCollection(input: $i) {
                   id reference txnType amount status customerName performedAt } }""",
            agent_tok,
            {"i": {"customerId": target["id"], "amount": "2500",
                   "purpose": "SAVINGS_CONTRIBUTION", "targetPlanId": plan["id"],
                   "idempotencyKey": f"e2e-coll-{int(time.time())}",
                   "deviceFingerprint": "e2e-full-cycle-001"}},
        )
        cd = (coll.get("data") or {}).get("agentCashCollection") or {}
        check("agentCashCollection SUCCESS", cd.get("status") == "SUCCESS",
              json.dumps(coll)[:300])
        if cd:
            print(f"        txn {cd['reference']} ₦{cd['amount']} -> {cd['customerName']}")

    print("[7] Paystack webhook rejects unsigned payloads")
    code, body = post(WEBHOOK, {
        "event": "charge.success",
        "data": {"id": 12345, "reference": "PAY-FAKE-1", "amount": 200000,
                 "status": "success", "currency": "NGN"},
    })
    check("unsigned webhook rejected (401)", code == 401, f"code={code} body={body}")

    print(f"\n== RESULT: {PASS} passed, {FAIL} failed ==")
    print(f"== Fresh test account: {phone} / Test#2026 ==")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()

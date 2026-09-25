#!/usr/bin/env python3
"""End-to-end workflow verification against the LIVE RFUND deployment.

Exercises the real business flows the deployment was asked to demonstrate:
  1. Login for every role (admin / KYC officer / agent / customers)
  2. Agent cash collection -> customer savings plan balance increases
  3. KYC submission (customer) -> admin review + approval (officer) -> VERIFIED
  4. Admin dashboard sanity

Usage: python3 e2e_vps_workflows.py [base_url]
       (default base: https://test.inyene.com — uses the public BFF)
"""
import json
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://test.inyene.com").rstrip("/")
API = f"{BASE}/api/graphql"

PASS_COUNT = 0
FAIL_COUNT = 0


def gql(query, token=None, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) RFUND-E2E/1.0",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def check(label, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  PASS  {label}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL  {label}  {detail}")


def login(phone, password):
    r = gql(
        "mutation($i: LoginInput!) { login(input: $i) { accessToken user { phone roles } } }",
        variables={"i": {"phone": phone, "password": password}},
    )
    return r["data"]["login"]["accessToken"], r["data"]["login"]["user"]["roles"]


def main():
    print(f"== RFUND live E2E against {BASE} ==")

    print("[1] Role logins")
    admin_tok, admin_roles = login("+2348000000000", "Admin#2026")
    check("admin login", "SUPER_ADMIN" in (admin_roles or []), admin_roles)
    kyc_tok, _ = login("+2348000000002", "Kyc#2026")
    agent_tok, _ = login("+2348000000100", "Agent#2026")
    cust1_tok, _ = login("+2348012345001", "Customer#2026")
    cust3_tok, _ = login("+2348012345003", "Customer#2026")
    print("  PASS  kyc-officer / agent / customer logins")

    print("[2] Agent cash collection funds the customer's savings plan")
    plans = gql(
        "query { savingsPlans(first: 10) { items { id reference productCode totalContributed status } } }",
        cust1_tok,
    )
    plan = next((p for p in plans["data"]["savingsPlans"]["items"] if p["productCode"] == "AJO_DAILY"), None)
    check("customer 5001 has AJO_DAILY plan", plan is not None, json.dumps(plans)[:200])
    before = plan["totalContributed"] if plan else None

    custs = gql(
        'query { agentCustomers(first: 20) { items { id phone fullName kycTier status } } }',
        agent_tok,
    )
    target = next((c for c in custs["data"]["agentCustomers"]["items"] if c["phone"] == "+2348012345001"), None)
    check("agent sees customer 5001 in territory", target is not None, json.dumps(custs)[:200])

    import time
    run_id = str(int(time.time()))
    coll = gql(
        """mutation($i: AgentCashCollectionInput!) {
             agentCashCollection(input: $i) {
               id reference txnType amount status customerName performedAt
             } }""",
        agent_tok,
        {"i": {
            "customerId": target["id"],
            "amount": "1500",
            "purpose": "SAVINGS_CONTRIBUTION",
            "targetPlanId": plan["id"],
            "idempotencyKey": f"vps-e2e-{plan['reference']}-{run_id}",
            "deviceFingerprint": "vps-e2e-device-001",
        }},
    )
    txn = coll.get("data", {}).get("agentCashCollection")
    check("agentCashCollection succeeded", bool(txn and txn["status"] == "SUCCESS"),
          json.dumps(coll.get("errors") or coll)[:300])
    print(f"        txn {txn['reference']} ₦{txn['amount']} -> {txn['customerName']}")

    plans_after = gql(
        "query { savingsPlans(first: 10) { items { id productCode totalContributed contributionCount } } }",
        cust1_tok,
    )
    plan_after = next((p for p in plans_after["data"]["savingsPlans"]["items"] if p["id"] == plan["id"]), None)
    check("plan totalContributed increased by 1500",
          plan_after and float(plan_after["totalContributed"]) == float(before) + 1500,
          f"before={before} after={plan_after and plan_after['totalContributed']}")
    print(f"        plan {plan['reference']}: {before} -> {plan_after['totalContributed']}")

    print("[3] KYC: submit -> review -> verified")
    cur = gql("query { kycStatus { status level verifiedAt } }", cust3_tok)
    already = cur["data"]["kycStatus"]["status"] in {"VERIFIED", "APPROVED"}
    if not already:
        sub = gql(
            "mutation($i: SubmitKYCInput!) { submitKyc(input: $i) { status level failureReason } }",
            cust3_tok,
            {"i": {"docType": "NIN", "idNumber": "98765432101"}},
        )
        sub_data = (sub.get("data") or {}).get("submitKyc") or {}
        check("customer 5003 submitted KYC", sub_data.get("status") in
              {"PENDING", "IN_REVIEW", "SUBMITTED"}, json.dumps(sub)[:400])
    else:
        print("  SKIP  customer 5003 already verified (previous run) — verifying review state")

    queue = gql(
        "query { adminKycQueue(first: 30) { items { id customerName status level submittedDocType } } }",
        kyc_tok,
    )
    qitems = queue.get("data", {}).get("adminKycQueue", {}).get("items", [])
    profile = next((p for p in qitems if "Funmilayo" in (p.get("customerName") or "")), None)
    if already and profile is None:
        print("  PASS  verified customer no longer pending in queue")
    else:
        check("KYC officer sees pending profile in queue", profile is not None, json.dumps(queue)[:400])
        if profile is None:
            print(f"\n== RESULT: {PASS_COUNT} passed, {FAIL_COUNT} failed ==")
            sys.exit(1)
        rev = gql(
            "mutation($i: ReviewKycInput!) { reviewKyc(input: $i) }",
            kyc_tok,
            {"i": {"profileId": profile["id"], "decision": "APPROVED",
                   "reason": "E2E verification", "newLevel": "STANDARD"}},
        )
        check("reviewKyc approved", rev.get("data", {}).get("reviewKyc") is True, json.dumps(rev)[:300])

    status = gql("query { kycStatus { status level verifiedAt } }", cust3_tok)
    check("customer 5003 kycStatus VERIFIED",
          status["data"]["kycStatus"]["status"] in {"VERIFIED", "APPROVED"}
          and status["data"]["kycStatus"]["level"] == "STANDARD",
          json.dumps(status)[:200])

    print("[4] Admin sanity")
    dash = gql(
        """query { adminDashboard {
               activeCustomers newCustomers7d savingsBalance activeSavingsPlans
               loanPortfolio activeLoans repaymentVolume30d interestIncome
               pendingKyc pendingLoanApplications paymentFailures24h
               reconciliationExceptions activeAgents agentCollectionsToday
               openFraudAlerts openSupportTickets
             } }""", admin_tok,
    )
    d = (dash.get("data") or {}).get("adminDashboard") or {}
    check("admin dashboard query", bool(d), json.dumps(dash)[:300])
    print(f"        customers={d.get('activeCustomers')} savingsBalance={d.get('savingsBalance')} "
          f"agents={d.get('activeAgents')} collectionsToday={d.get('agentCollectionsToday')}")

    print(f"\n== RESULT: {PASS_COUNT} passed, {FAIL_COUNT} failed ==")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()

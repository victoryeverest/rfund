#!/usr/bin/env python3
"""End-to-end API smoke test against the running backend (sandbox verification)."""

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def gql(query, token=None, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{BASE}/graphql", data=body, headers={"Content-Type": "application/json"}
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def health():
    for path in ("/health/live", "/health/ready"):
        with urllib.request.urlopen(f"{BASE}{path}") as resp:
            print(f"  {path}: {resp.status} {json.loads(resp.read())}")


def main():
    print("== Health ==")
    health()

    print("== Auth: login customer ==")
    r = gql(
        """
        mutation Login($input: LoginInput!) {
          login(input: $input) {
            accessToken refreshToken expiresInMinutes
            user { id phone firstName lastName }
          }
        }
        """,
        variables={"input": {"phone": "+2348012345001", "password": "Customer#2026"}},
    )
    if r.get("errors"):
        print("  LOGIN FAILED:", r["errors"])
        return 1
    login = r["data"]["login"]
    token = login["accessToken"]
    print(f"  token ok, user: {login['user']['firstName']} {login['user']['lastName']}")

    print("== Query: me + dashboard ==")
    r = gql(
        """
        { me { customerReference fullName phone status kycTier }
           dashboard { savings { totalSaved activePlans nextContributionDate }
                       loan { reference outstanding } goalsCount }
           kycStatus { status level } }
        """,
        token=token,
    )
    if r.get("errors"):
        print("  ME FAILED:", r["errors"])
        return 1
    print("  me:", json.dumps(r["data"]["me"], indent=None))
    print("  dashboard:", json.dumps(r["data"]["dashboard"], indent=None))
    print("  kyc:", r["data"]["kycStatus"]["status"], r["data"]["kycStatus"]["level"])

    print("== Query: savings plans + schedule ==")
    r = gql(
        """
        { savingsPlans(first: 5) { items { reference amount frequency status
              totalContributed contributionCount contributionsPaid nextDue { dueDate amount status } }
              pageInfo { totalCount } } }
        """,
        token=token,
    )
    if r.get("errors"):
        print("  SAVINGS FAILED:", r["errors"])
        return 1
    for plan in r["data"]["savingsPlans"]["items"]:
        print(f"  plan {plan['reference']}: ₦{plan['amount']} {plan['frequency']} "
              f"[{plan['contributionsPaid']}/{plan['contributionCount']}] next={plan['nextDue']}")

    print("== Mutation: create savings goal ==")
    r = gql(
        """
        mutation { createSavingsGoal(input: { name: "School fees", targetAmount: "50000",
             targetDate: "2027-06-30", contributionFrequency: "MONTHLY", contributionAmount: "5000" }) {
             id name targetAmount currentAmount status progressPct } }
        """,
        token=token,
    )
    if r.get("errors"):
        print("  GOAL FAILED:", r["errors"])
        return 1
    print("  goal:", json.dumps(r["data"]["createSavingsGoal"]))

    print("== Mutation: make payment (initialize) ==")
    r = gql(
        """
        mutation { makePayment(input: { purpose: "ACCOUNT_FUNDING", amount: "2000",
              idempotencyKey: "smoke-test-001" }) {
              payment { reference amount status provider } authorizationUrl } }
        """,
        token=token,
    )
    if r.get("errors"):
        print("  PAYMENT FAILED:", r["errors"])
        return 1
    print("  payment:", json.dumps(r["data"]["makePayment"]["payment"]))

    print("== Admin: login + dashboard + ledger ==")
    r = gql(
        """
        mutation { login(input: { phone: "+2348000000000", password: "Admin#2026" }) { accessToken } }
        """
    )
    admin_token = r["data"]["login"]["accessToken"]
    r = gql(
        """
        { adminDashboard { activeCustomers savingsBalance loanPortfolio activeAgents
              pendingKyc openFraudAlerts reconciliationExceptions }
           adminLedgerAccounts { code type balance status } }
        """,
        token=admin_token,
    )
    if r.get("errors"):
        print("  ADMIN FAILED:", r["errors"])
        return 1
    print("  dashboard:", json.dumps(r["data"]["adminDashboard"]))
    for acct in r["data"]["adminLedgerAccounts"]:
        print(f"    {acct['code']:22s} {acct['type']:10s} ₦{acct['balance']:>12s} {acct['status']}")

    print("== Security: customer cannot access admin fields ==")
    r = gql("{ adminDashboard { activeCustomers } }", token=token)
    if r.get("errors") and any(e.get("extensions", {}).get("code") == "FORBIDDEN" for e in r["errors"]):
        print("  correctly FORBIDDEN for customer ✓")
    elif r.get("errors"):
        print("  blocked with:", r["errors"][0].get("extensions", {}).get("code"))
    else:
        print("  !!! SECURITY FAILURE: customer saw admin data !!!")
        return 1

    print("== Depth limiting ==")
    deep = "{ me { " + "savingsPlans { items { " * 12 + "reference" + " } } " * 12 + " } }"
    try:
        req = urllib.request.Request(
            f"{BASE}/graphql",
            data=json.dumps({"query": deep}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
        if resp.status == 400 or (body.get("errors") and "depth" in body["errors"][0]["message"].lower()):
            print("  deep query correctly rejected ✓")
        else:
            print("  deep query result:", body)
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print("  deep query correctly rejected (400) ✓")

    print("\nALL SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

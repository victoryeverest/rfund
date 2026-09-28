#!/usr/bin/env python3
"""Loan application retest with correct schema fields + admin decision flow."""
import json
import sys
import time
import urllib.request
import urllib.error

API = "https://testapi.inyene.com/graphql"
PHONE = sys.argv[1] if len(sys.argv) > 1 else "+2348012377438"

PASS = FAIL = 0


def gql(query, token=None, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 RFUND-E2E/1.0",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def main():
    print(f"== Loan flow retest for {PHONE} ==")
    tok = gql(
        "mutation($i: LoginInput!) { login(input: $i) { accessToken } }",
        variables={"i": {"phone": PHONE, "password": "Test#2026"}},
    )["data"]["login"]["accessToken"]

    loan = gql(
        "mutation($i: ApplyForLoanInput!) { applyForLoan(input: $i) { id reference amountRequested state productCode productName submittedAt } }",
        tok, {"i": {"productCode": "TRADER", "amount": "25000",
                     "termMonths": 6, "purpose": "E2E full-cycle",
                     "monthlyIncome": "120000"}},
    )
    ld = (loan.get("data") or {}).get("applyForLoan") or {}
    check("applyForLoan submitted", bool(ld.get("reference")), json.dumps(loan)[:300])
    if ld:
        print(f"        loan {ld['reference']} ₦{ld['amountRequested']} state={ld['state']} product={ld['productName']}")

    # Customer sees their applications
    apps = gql(
        "query { loanApplications(first: 10) { items { reference amountRequested state } } }",
        tok,
    )
    items = (apps.get("data") or {}).get("loanApplications", {}).get("items", [])
    check("customer sees own applications", any(i.get("reference") == ld.get("reference") for i in items),
          json.dumps(apps)[:200])

    # Admin decides the application
    admin_tok = gql(
        "mutation($i: LoginInput!) { login(input: $i) { accessToken } }",
        variables={"i": {"phone": "+2348000000000", "password": "Admin#2026"}},
    )["data"]["login"]["accessToken"]

    admin_apps = gql(
        "query { adminLoanApplications(first: 20) { items { id reference customerName amountRequested state } } }",
        admin_tok,
    )
    aitems = (admin_apps.get("data") or {}).get("adminLoanApplications", {}).get("items", [])
    target = next((a for a in aitems if a.get("reference") == ld.get("reference")), None)
    check("admin sees the application", target is not None, json.dumps(admin_apps)[:300])

    if target:
        dec = gql(
            "mutation($i: LoanDecisionInput!) { decideLoanApplication(input: $i) { id reference state } }",
            admin_tok, {"i": {"applicationId": target["id"], "approve": True,
                               "reason": "E2E approval", "amount": "25000",
                               "termMonths": 6}},
        )
        dd = (dec.get("data") or {}).get("decideLoanApplication") or {}
        check("decideLoanApplication APPROVED", dd.get("state") in {"APPROVED", "OFFERED"},
              json.dumps(dec)[:300])
        if dd:
            print(f"        decision: {dd['reference']} -> {dd['state']}")

    # Final state check
    fin = gql(
        "query { loanApplications(first: 10) { items { reference state amountRequested } } }",
        tok,
    )
    fitems = (fin.get("data") or {}).get("loanApplications", {}).get("items", [])
    final = next((f for f in fitems if f.get("reference") == ld.get("reference")), None)
    check("final state APPROVED/OFFERED", final and final.get("state") in {"APPROVED", "OFFERED"},
          json.dumps(fin)[:200])

    print(f"\n== RESULT: {PASS} passed, {FAIL} failed ==")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()

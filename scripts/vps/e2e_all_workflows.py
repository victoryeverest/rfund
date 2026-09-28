#!/usr/bin/env python3
"""ALL-WORKFLOWS E2E — roles, savings, KYC, loans, agents, admin, Paystack.

Stage 1 (API): fresh customer + existing agent/admin/officer logins, savings
plan + goal, KYC full cycle, loan apply->decide->accept->disburse, agent
collection, agent settlement request, admin dashboard/payments/ledger checks,
and initializes TWO real Paystack hosted-checkout payments (savings
contribution + loan repayment). Writes state to /tmp/e2e_state.json and
prints the checkout URLs for browser completion.

Stage 3 (API): after the browser completes both checkouts — verifies payment
SUCCESS, plan credit, loan repayment application, ledger, admin views.
"""
import json
import sys
import time
import urllib.error
import urllib.request

API = "https://testapi.inyene.com/graphql"
STATE_FILE = "/tmp/e2e_state.json"
PASS = FAIL = 0


def post(url, body, token=None):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json",
               "User-Agent": "Mozilla/5.0 RFUND-E2E/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
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


def login(phone, password):
    r = gql("mutation($i: LoginInput!) { login(input: $i) { accessToken user { phone roles } } }",
            variables={"i": {"phone": phone, "password": password}})
    d = (r.get("data") or {}).get("login") or {}
    return d.get("accessToken"), (d.get("user") or {}).get("roles")


def stage1():
    state = {}
    phone = f"+23480123{int(time.time()) % 100000:05d}"
    print(f"== STAGE 1 — fresh account {phone} ==")

    print("[1] Users for every role")
    reg = gql("mutation($i: RegisterInput!) { registerCustomer(input: $i) { accessToken user { phone roles } } }",
              variables={"i": {"phone": phone, "password": "Test#2026",
                               "firstName": "Full", "lastName": "Workflow"}})
    tok = (reg.get("data") or {}).get("registerCustomer", {}).get("accessToken")
    check("customer registered (fresh user)", bool(tok), json.dumps(reg)[:200])
    tok, roles = login(phone, "Test#2026")
    check("customer login", bool(tok) and roles == ["CUSTOMER"], f"{roles}")
    state["phone"], state["password"], state["customer_token"] = phone, "Test#2026", tok

    agent_tok, aroles = login("+2348000000100", "Agent#2026")
    check("agent/merchant login", bool(agent_tok) and "AGENT" in (aroles or []), f"{aroles}")
    admin_tok, mroles = login("+2348000000000", "Admin#2026")
    check("admin login", bool(admin_tok) and ("ADMIN" in (mroles or []) or "SUPER_ADMIN" in (mroles or [])), f"{mroles}")
    kyc_tok, kroles = login("+2348000000002", "Kyc#2026")
    check("KYC officer login", bool(kyc_tok), f"{kroles}")
    state["agent_token"], state["admin_token"], state["kyc_token"] = agent_tok, admin_tok, kyc_tok

    print("[2] Savings features")
    from datetime import date, timedelta
    start, end = date.today().isoformat(), (date.today() + timedelta(days=90)).isoformat()
    plan_m = gql("mutation($i: CreateSavingsPlanInput!) { createSavingsPlan(input: $i) { id reference status } }",
                 tok, {"i": {"productCode": "SAVE_FLEX", "amount": "5000",
                             "frequency": "MONTHLY", "startDate": start, "endDate": end}})
    plan = (plan_m.get("data") or {}).get("createSavingsPlan") or {}
    check("create savings plan", bool(plan.get("reference")), json.dumps(plan_m)[:250])
    state["plan_id"], state["plan_ref"] = plan.get("id"), plan.get("reference")

    goal_m = gql("mutation($i: CreateGoalInput!) { createSavingsGoal(input: $i) { id name status } }",
                 tok, {"i": {"name": "E2E Shop Goal", "targetAmount": "20000",
                             "contributionFrequency": "MONTHLY", "contributionAmount": "2000"}})
    goal = (goal_m.get("data") or {}).get("createSavingsGoal") or {}
    check("create savings goal", bool(goal.get("id")), json.dumps(goal_m)[:250])
    state["goal_id"] = goal.get("id")

    dash = gql("query { dashboard { savings { totalSaved activePlans } goalsCount } }", tok)
    sd = (dash.get("data") or {}).get("dashboard", {}).get("savings", {})
    check("dashboard reflects 1 active plan", sd.get("activePlans") == 1, json.dumps(dash)[:200])

    print("[3] KYC full cycle")
    sub = gql("mutation($i: SubmitKYCInput!) { submitKyc(input: $i) { status level } }",
              tok, {"i": {"docType": "NIN", "idNumber": f"77{int(time.time()) % 10**9:09d}"}})
    check("submitKyc", (sub.get("data") or {}).get("submitKyc", {}).get("status") is not None,
          json.dumps(sub)[:250])
    queue = gql("query { adminKycQueue(first: 50) { items { id customerName status } } }", kyc_tok)
    items = ((queue.get("data") or {}).get("adminKycQueue") or {}).get("items", [])
    profile = next((p for p in items if "Full" in (p.get("customerName") or "")), None)
    check("officer sees fresh KYC", profile is not None, json.dumps(queue)[:200])
    rev = gql("mutation($i: ReviewKycInput!) { reviewKyc(input: $i) }", kyc_tok,
              {"i": {"profileId": profile["id"], "decision": "APPROVED",
                     "reason": "All-workflows E2E", "newLevel": "STANDARD"}})
    check("reviewKyc APPROVED", (rev.get("data") or {}).get("reviewKyc") is True, json.dumps(rev)[:200])
    st = gql("query { kycStatus { status level } }", tok)
    kd = (st.get("data") or {}).get("kycStatus", {})
    check("customer now VERIFIED/STANDARD",
          kd.get("status") == "VERIFIED" and kd.get("level") == "STANDARD", json.dumps(st)[:200])

    print("[4] Loans: apply -> decide -> accept -> disburse")
    elig = gql("query { loanEligibility(productCode: \"TRADER\", amount: \"25000\", termMonths: 6) { eligible reasons } }", tok)
    check("loanEligibility query works", "data" in elig, json.dumps(elig)[:200])
    loan = gql("mutation($i: ApplyForLoanInput!) { applyForLoan(input: $i) { id reference state } }",
               tok, {"i": {"productCode": "TRADER", "amount": "25000", "termMonths": 6,
                           "purpose": "All-workflows E2E", "monthlyIncome": "120000",
                           "businessName": "Full Workflow Traders"}})
    app = (loan.get("data") or {}).get("applyForLoan") or {}
    check("applyForLoan submitted", bool(app.get("reference")), json.dumps(loan)[:250])
    state["application_id"], state["loan_ref"] = app.get("id"), app.get("reference")

    apps = gql("query { adminLoanApplications(state: \"SUBMITTED\", first: 30) { items { id reference customerName } } }", admin_tok)
    listed = [a for a in ((apps.get("data") or {}).get("adminLoanApplications") or {}).get("items", [])
              if a.get("reference") == state.get("loan_ref")]
    check("admin sees SUBMITTED application", bool(listed), json.dumps(apps)[:250])

    dec = gql("mutation($i: LoanDecisionInput!) { decideLoanApplication(input: $i) { id state } }", admin_tok,
              {"i": {"applicationId": state["application_id"], "approve": True,
                     "reason": "E2E approve", "amount": "25000", "termMonths": 6}})
    check("decideLoanApplication APPROVE", (dec.get("data") or {}).get("decideLoanApplication", {}).get("state") == "OFFERED",
          json.dumps(dec)[:250])
    acc = gql("mutation($a: ID!) { acceptLoanOffer(applicationId: $a) { id state } }", tok,
              {"a": state["application_id"]})
    check("acceptLoanOffer", (acc.get("data") or {}).get("acceptLoanOffer", {}).get("state") in ("ACCEPTED", "APPROVED"),
          json.dumps(acc)[:250])
    dis = gql("mutation($a: ID!) { disburseLoan(applicationId: $a) { id state } }", admin_tok,
              {"a": state["application_id"]})
    check("disburseLoan accepted", (dis.get("data") or {}).get("disburseLoan") is not None,
          json.dumps(dis)[:250])
    loans = gql("query { loans(first: 5) { id reference status totalOutstanding } }", tok)
    loan_items = (loans.get("data") or {}).get("loans", [])
    loan_rec = loan_items[0] if loan_items else None  # fresh customer has exactly one loan
    check("loan ACTIVE with outstanding", loan_rec and loan_rec.get("status") in ("ACTIVE", "DISBURSED"),
          json.dumps(loans)[:250])
    state["loan_id"] = loan_rec["id"] if loan_rec else None
    state["loan_record_ref"] = loan_rec.get("reference") if loan_rec else None

    print("[5] Agent collection + settlement")
    custs = gql("query { agentCustomers(first: 100) { items { id phone fullName } } }", agent_tok)
    target = next((c for c in ((custs.get("data") or {}).get("agentCustomers") or {}).get("items", [])
                   if c["phone"] == phone), None)
    check("agent finds fresh customer", target is not None, json.dumps(custs)[:200])
    coll = gql("""mutation($i: AgentCashCollectionInput!) { agentCashCollection(input: $i) {
                   reference amount status customerName } }""", agent_tok,
               {"i": {"customerId": target["id"], "amount": "2500",
                      "purpose": "SAVINGS_CONTRIBUTION", "targetPlanId": state["plan_id"],
                      "idempotencyKey": f"e2e-all-coll-{int(time.time())}",
                      "deviceFingerprint": "e2e-all-001"}})
    cd = (coll.get("data") or {}).get("agentCashCollection") or {}
    check("agent cash collection SUCCESS", cd.get("status") == "SUCCESS", json.dumps(coll)[:250])

    settle = gql("mutation($a: String) { requestAgentSettlement(amount: $a) { id reference amount status } }",
                 agent_tok, {"a": "1000"})
    check("agent settlement requested", (settle.get("data") or {}).get("requestAgentSettlement", {}).get("status") is not None,
          json.dumps(settle)[:250])

    print("[6] Admin live views")
    adm = gql("query { adminDashboard { activeCustomers savingsBalance loanPortfolio agentCollectionsToday pendingKyc } }", admin_tok)
    check("adminDashboard", (adm.get("data") or {}).get("adminDashboard") is not None, json.dumps(adm)[:200])
    led = gql("query { adminLedgerTransactions(first: 10) { items { reference transactionType status } } }", admin_tok)
    check("adminLedgerTransactions", (led.get("data") or {}).get("adminLedgerTransactions") is not None,
          json.dumps(led)[:200])

    print("[7] Initialize REAL Paystack checkouts (complete in browser)")
    pay1 = gql("""mutation($i: MakePaymentInput!) { makePayment(input: $i) {
                   payment { id reference amount } authorizationUrl } }""", tok,
               {"i": {"purpose": "SAVINGS_CONTRIBUTION", "amount": "1000",
                      "targetPlanId": state["plan_id"],
                      "idempotencyKey": f"e2e-all-pay1-{int(time.time())}"}})
    p1 = (pay1.get("data") or {}).get("makePayment") or {}
    check("Paystack savings checkout URL returned",
          bool(p1.get("authorizationUrl", "").startswith("https://checkout.paystack.com")),
          json.dumps(pay1)[:300])
    state["savings_payment_id"] = (p1.get("payment") or {}).get("id")
    state["savings_payment_ref"] = (p1.get("payment") or {}).get("reference")
    state["savings_checkout_url"] = p1.get("authorizationUrl")

    pay2 = gql("""mutation($i: MakePaymentInput!) { makePayment(input: $i) {
                   payment { id reference amount } authorizationUrl } }""", tok,
               {"i": {"purpose": "LOAN_REPAYMENT", "amount": "5000",
                      "targetLoanId": state["loan_id"],
                      "idempotencyKey": f"e2e-all-pay2-{int(time.time())}"}})
    p2 = (pay2.get("data") or {}).get("makePayment") or {}
    check("Paystack loan-repayment checkout URL returned",
          bool(p2.get("authorizationUrl", "").startswith("https://checkout.paystack.com")),
          json.dumps(p2)[:300])
    state["loan_payment_id"] = (p2.get("payment") or {}).get("id")
    state["loan_payment_ref"] = (p2.get("payment") or {}).get("reference")
    state["loan_checkout_url"] = p2.get("authorizationUrl")

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"\nState saved to {STATE_FILE}")
    print(f"SAVINGS_CHECKOUT={state.get('savings_checkout_url')}")
    print(f"LOAN_CHECKOUT={state.get('loan_checkout_url')}")
    print(f"== STAGE 1 RESULT: {PASS} passed, {FAIL} failed ==")
    return 1 if FAIL else 0


def stage3():
    with open(STATE_FILE) as f:
        state = json.load(f)
    tok = state["customer_token"]
    print("== STAGE 3 — post-checkout verification ==")

    print("[A] Savings payment settled")
    pay = gql("query($id: ID!) { payment(id: $id) { id reference status amount method completedAt } }",
              tok, {"id": state["savings_payment_id"]})
    p = (pay.get("data") or {}).get("payment") or {}
    check("savings payment SUCCESS", p.get("status") == "SUCCESS", json.dumps(pay)[:300])
    if p.get("completedAt"):
        print(f"        {p['reference']} ₦{p['amount']} via {p['method']} at {p['completedAt']}")

    plan = gql("query($id: ID!) { savingsPlan(id: $id) { reference status totalContributed contributionsPaid contributionCount } }",
               tok, {"id": state["plan_id"]})
    pl = (plan.get("data") or {}).get("savingsPlan") or {}
    check("plan credited by card payment (totalContributed >= 3500 = 2500 agent + 1000 card)",
          float(pl.get("totalContributed") or 0) >= 3500, json.dumps(plan)[:300])

    dash = gql("query { dashboard { savings { totalSaved activePlans } } }", tok)
    sd = (dash.get("data") or {}).get("dashboard", {}).get("savings", {})
    check("dashboard Money saved >= 3500", float(sd.get("totalSaved") or 0) >= 3500,
          json.dumps(dash)[:200])

    print("[B] Loan repayment settled")
    pay2 = gql("query($id: ID!) { payment(id: $id) { id reference status amount completedAt } }",
               tok, {"id": state["loan_payment_id"]})
    p2 = (pay2.get("data") or {}).get("payment") or {}
    check("loan repayment payment SUCCESS", p2.get("status") == "SUCCESS", json.dumps(pay2)[:300])

    loan = gql("query($id: ID!) { loan(id: $id) { reference status totalOutstanding repaymentSchedule(loanId: $id, first: 60) { items { sequence amountPaid status } } } }",
               tok, {"id": state["loan_id"]})
    ln = (loan.get("data") or {}).get("loan") or {}
    check("loan repayment applied to schedule (₦5,000 card payment)",
          any(float(i.get("amountPaid") or 0) > 0 for i in ((ln.get("repaymentSchedule") or {}).get("items") or [])),
          json.dumps(loan)[:400])

    print("[C] Admin sees the card payments")
    admin_tok = state["admin_token"]
    pays = gql("query { adminPayments(first: 30) { items { reference customerName purpose amount status provider } } }", admin_tok)
    items = ((pays.get("data") or {}).get("adminPayments") or {}).get("items", [])
    mine = [p for p in items if p.get("reference") in (state.get("savings_payment_ref"), state.get("loan_payment_ref"))]
    check("admin payments list shows both card payments", len(mine) >= 2, json.dumps([m.get("reference") for m in mine]))

    led = gql("query { adminLedgerTransactions(first: 30) { items { reference transactionType status entries { accountCode direction amount } } } }", admin_tok)
    ltx = ((led.get("data") or {}).get("adminLedgerTransactions") or {}).get("items", [])
    card_tx = [t for t in ltx if t.get("reference") in (state.get("savings_payment_ref"), state.get("loan_payment_ref"))]
    check("ledger posted for card payments", len(card_tx) >= 2,
          json.dumps([t.get("reference") for t in ltx[:6]])[:300])

    print("[D] Transactions feed (customer)")
    txns = gql("query { payments(first: 10) { items { reference purpose amount status method } } }", tok)
    items = ((txns.get("data") or {}).get("payments") or {}).get("items", [])
    card_items = [t for t in items if t.get("method") == "CARD"]
    check("customer transactions include CARD entries", len(card_items) >= 2, json.dumps(txns)[:300])

    print(f"== STAGE 3 RESULT: {PASS} passed, {FAIL} failed ==")
    print(f"== Test users: customer {state['phone']}/{state['password']} · agent +2348000000100/Agent#2026 · admin +2348000000000/Admin#2026 ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stage1"
    sys.exit(stage1() if mode == "stage1" else stage3())

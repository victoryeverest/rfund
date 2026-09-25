#!/usr/bin/env bash
# E2E verification of the new admin pages + OTP login + notifications.
# Runs everything in ONE process lifetime: start next -> verify -> shutdown.
set -u
cd /home/z/my-project

echo "== starting next (production build) =="
setsid nohup bun run start > /tmp/next_e2e.log 2>&1 < /dev/null &
NEXT_PID=$!
for i in $(seq 1 45); do
  sleep 1
  if curl -s -o /dev/null --max-time 2 http://localhost:3000/; then break; fi
done
curl -s -o /dev/null -w "next http: %{http_code}\n" http://localhost:3000/ || { echo "NEXT FAILED"; tail -20 /tmp/next_e2e.log; kill $NEXT_PID 2>/dev/null; exit 1; }

echo "== backend health =="
curl -s -o /dev/null -w "django graphql: %{http_code}\n" -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" -d '{"query":"{ __schema { queryType { name } } }"}'

echo "== admin login =="
TOKEN=$(curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
  -d '{"query":"mutation { login(input: { phone: \"+2348000000000\", password: \"Admin#2026\", deviceLabel: \"e2e\" }) { accessToken user { firstName } } }"}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['login']['accessToken'])")
echo "admin token: ${TOKEN:0:24}..."

echo "== GraphQL: all new/formerly-orphaned admin queries =="
for Q in \
  'query { adminAgents(first: 5) { items { agentCode businessName status } pageInfo { totalCount } } }' \
  'query { adminAuditEvents(first: 5) { items { actorLabel action resourceType } totalCount } }' \
  'query { adminFraudAlerts(first: 5) { items { ruleCode severity status } } }' \
  'query { adminLedgerAccounts { code name type balance } }' \
  'query { adminLoanApplications(first: 5) { items { reference customerName state } } }' \
  'query { adminPayments(first: 5) { items { reference status amount } } }' \
  'query { adminReconciliationRuns(first: 5) { provider status } adminReconciliationExceptions(first: 5) { internalReference resolved } }' \
  'query { adminSupportTickets(first: 5) { items { reference status priority } } }' \
  'query { adminWebhooks(first: 5) { items { provider eventType processingStatus } } }' \
  'query { adminReport(reportType: "agent_performance") }' \
  ; do
  LABEL=$(echo "$Q" | grep -o 'admin[A-Za-z]*' | head -1)
  ERR=$(curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" -d "$(python3 -c "import json,sys; print(json.dumps({'query': sys.argv[1]}))" "$Q")" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('ERRORS: ' + str(d.get('errors')) if d.get('errors') else 'OK')")
  echo "  $LABEL → $ERR"
done

echo "== customer login + notifications + OTP =="
CTOKEN=$(curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
  -d '{"query":"mutation { login(input: { phone: \"+2348012345001\", password: \"Customer#2026\", deviceLabel: \"e2e\" }) { accessToken } }"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['login']['accessToken'])")
echo "customer token: ${CTOKEN:0:24}..."

curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CTOKEN" \
  -d '{"query":"{ notifications { items { eventCode label amount reference dispatched } totalCount } }"}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); n=d.get('errors') and print('ERRORS', d['errors']) or (lambda: None)(); f=(d.get('data') or {}).get('notifications'); print('notifications totalCount:', f and f['totalCount'])"

echo "== OTP login flow (dev devCode) =="
curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
  -d '{"query":"mutation { requestOtp(phone: \"+2348012345001\", purpose: \"LOGIN\") { sent devCode } }"}' > /tmp/otp.json
DEVcode=$(python3 -c "import json; print(json.load(open('/tmp/otp.json'))['data']['requestOtp']['devCode'] or '')")
echo "devCode present: $([ -n "$DEVcode" ] && echo yes || echo no)"
if [ -n "$DEVcode" ]; then
  curl -s -X POST http://localhost:8000/graphql -H "Content-Type: application/json" \
    -d "$(python3 -c "import json; print(json.dumps({'query': 'mutation($p: String!, $c: String!) { loginWithOtp(phone: $p, code: $c) { accessToken user { phone } } }', 'variables': {'p': '+2348012345001', 'c': '$DEVcode'}}))")" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); r=(d.get('data') or {}).get('loginWithOtp'); print('loginWithOtp:', 'OK user=' + r['user']['phone'] if r and r.get('accessToken') else 'FAILED ' + str(d.get('errors')))"
fi

echo "== frontend routes (SSR check via HTTP status) =="
for route in / /login /admin/dashboard /admin/customers /admin/kyc /admin/loans /admin/payments /admin/ledger /admin/reconciliation /admin/agents /admin/fraud /admin/support /admin/reports /admin/audit /app/dashboard /app/notifications; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://localhost:3000$route")
  echo "  $route → $CODE"
done

kill $NEXT_PID 2>/dev/null
pkill -f "next start" 2>/dev/null
echo "== E2E DONE =="

#!/usr/bin/env python3
"""Create the goal-funding payment for the charge-API completion test."""
import json
import urllib.request

state = json.load(open('/tmp/e2e_state.json'))
tok = state['customer_token']
q = ('mutation($i: MakePaymentInput!) { makePayment(input: $i) '
     '{ payment { id reference amount } authorizationUrl } }')
variables = {'i': {'purpose': 'GOAL_FUNDING', 'amount': '500',
                   'targetGoalId': state['goal_id'],
                   'idempotencyKey': 'e2e-goal-card-1'}}
body = json.dumps({'query': q, 'variables': variables}).encode()
req = urllib.request.Request(
    'https://testapi.inyene.com/graphql', data=body,
    headers={'Content-Type': 'application/json',
             'Authorization': f'Bearer {tok}',
             'User-Agent': 'Mozilla/5.0 RFUND-E2E/1.0'})
r = json.loads(urllib.request.urlopen(req, timeout=30).read())
d = (r.get('data') or {}).get('makePayment') or {}
print(json.dumps(r, indent=2)[:500])
if d.get('payment'):
    state['goal_payment_id'] = d['payment']['id']
    state['goal_payment_ref'] = d['payment']['reference']
    json.dump(state, open('/tmp/e2e_state.json', 'w'), indent=2)
    print('SAVED goal_payment_ref =', state['goal_payment_ref'])

# Paystack status — RFUND test deployment (UPDATED 2026-09-28)

## ACTIVATED

Test keys are configured and verified live:

- PAYSTACK_SECRET_KEY / PAYSTACK_PUBLIC_KEY / PAYSTACK_WEBHOOK_SECRET are set
  in /opt/rfund/rfund.env (test keys, sk_test_/pk_test_).
- PAYMENT_CALLBACK_BASE=https://test.inyene.com — after checkout the customer
  lands on /app/payments/return which verifies server-side.
- Verified end-to-end on 2026-09-28:
  - makePayment returns a real checkout.paystack.com authorization URL
  - charge.success webhook with valid signature settles the payment, posts
    the ledger entry, credits the savings plan / goal / loan repayment
  - admin payments page shows the payments and the processed webhook events
  - the /app/payments/return page confirms "Payment received" with the ref

## Remaining (user, ~1 minute, optional but recommended)

Register the webhook URL in the Paystack dashboard so Paystack pushes
charge.success events automatically (until then, payments still complete via
the server-side verification on the return page):

- Sign in at https://dashboard.paystack.com
- Settings -> API Keys & Webhooks -> Webhook URL:

    https://testapi.inyene.com/payments/webhooks/paystack

The endpoint verifies the x-paystack-signature HMAC-SHA512 header and never
trusts browser claims (server-side verification is authoritative).

## Try it

Log in as a saver (e.g. +2348012386044 / Test#2026 — the full-workflow E2E
account — or +2348012345001 / Customer#2026), open a savings plan or the
Payments page, and fund with a card. In TEST mode use Paystack test cards:

    4084 0840 8408 4081  (success, any future expiry, CVV 408, OTP 123456)

Note: automated/headless browsers are challenged by Cloudflare on
checkout.paystack.com — complete the checkout in a normal browser.

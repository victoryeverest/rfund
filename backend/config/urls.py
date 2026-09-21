"""URL configuration.

The application API is GraphQL (spec §5). Plain Django views exist only for:
  - health/readiness endpoints (spec §169)
  - the payment webhook (spec §25 — webhooks are provider-to-server HTTP)
"""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from apps.core.views import health_live, health_ready
from apps.payments.views import paystack_webhook
from graphql_api.schema import schema
from graphql_api.view import RfundGraphQLView

urlpatterns = [
    path("health/live", health_live, name="health-live"),
    path("health/ready", health_ready, name="health-ready"),
    path("payments/webhooks/paystack", csrf_exempt(paystack_webhook), name="paystack-webhook"),
    path("graphql", csrf_exempt(RfundGraphQLView(schema)), name="graphql"),
]

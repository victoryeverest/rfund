"""Bootstrap test logins + catalog for a deployment (operator utility).

Run ONLY on test/staging deployments with explicit opt-in:

    cd backend
    RFUND_BOOTSTRAP_DEMO=true ../../venv/bin/python manage.py shell < ../scripts/vps/bootstrap_test_data.py

Creates the documented demo logins (see README):
  - super admin   +2348000000000 / Admin#2026
  - KYC officer   +2348000000002 / Kyc#2026
  - agent         +2348000000100 / Agent#2026
  - customers     +2348012345001..5003 / Customer#2026

plus RBAC, core ledger accounts, savings/loan products, territories,
crops, and a cooperative. Does NOT create fake transactions or provider
webhook events — fund plans through the real workflows (agent cash
collection, Paystack) so the audit trail stays truthful.
"""

import os
from datetime import date, timedelta
from decimal import Decimal

if os.environ.get("RFUND_BOOTSTRAP_DEMO") != "true":
    raise SystemExit(
        "Refusing: set RFUND_BOOTSTRAP_DEMO=true to run (test deployments only)."
    )

from apps.accounts.models import User
from apps.accounts.services import bootstrap_rbac, grant_role
from apps.agents import services as agent_services
from apps.agents.models import Agent, AgentTerritory
from apps.agriculture.models import Crop
from apps.cooperatives.models import Cooperative, CooperativeMember
from apps.customers import services as customer_services
from apps.customers.models import Customer
from apps.farmers.models import FarmerProfile, Farm
from apps.fraud.services import ensure_default_rules
from apps.identity import services as kyc_services
from apps.ledger.services import ensure_core_accounts
from apps.loans import services as loan_services
from apps.notifications.services import ensure_default_templates
from apps.organizations.models import Organization
from apps.risk.services import ensure_default_rules as ensure_risk_rules
from apps.savings import services as savings_services
from apps.savings.models import SavingsPlan

print("Bootstrapping RBAC, core accounts, rules, templates, products ...")
bootstrap_rbac()
ensure_core_accounts()
ensure_risk_rules()
ensure_default_rules()
ensure_default_templates()
savings_services.ensure_default_products()
loan_services.ensure_default_products()

print("Bootstrapping territories & crops ...")
for code, state, lga in [
    ("KJ-A1", "Kaduna", "Zaria"),
    ("KN-D2", "Kano", "Dawakin Tofa"),
    ("OY-I3", "Oyo", "Ibadan North"),
    ("EN-N4", "Enugu", "Nsukka"),
]:
    AgentTerritory.objects.get_or_create(
        code=code, defaults={"state": state, "lga": lga, "communities": []}
    )
for code, name in [
    ("MAIZE", "Maize"), ("RICE", "Rice"), ("CASSAVA", "Cassava"),
    ("YAM", "Yam"), ("TOMATO", "Tomato"), ("MILLET", "Millet"),
    ("SORGHUM", "Sorghum"), ("GROUNDNUT", "Groundnut"),
]:
    Crop.objects.get_or_create(code=code, defaults={"name": name})

# -- Super admin -----------------------------------------------------------
if not User.objects.filter(phone="+2348000000000").exists():
    admin = User.objects.create_user(
        phone="+2348000000000",
        password="Admin#2026",
        first_name="Platform",
        last_name="Admin",
        email="admin@rfund.example",
        is_staff=True,
    )
    grant_role(admin, "SUPER_ADMIN")
    print("  super admin: +2348000000000 / Admin#2026")

# -- KYC officer (reviews KYC in the admin workflow) ------------------------
kyc_officer = None
if not User.objects.filter(phone="+2348000000002").exists():
    kyc_officer = User.objects.create_user(
        phone="+2348000000002",
        password="Kyc#2026",
        first_name="KYC",
        last_name="Officer",
        email="kyc@rfund.example",
    )
    grant_role(kyc_officer, "KYC_OFFICER")
    print("  kyc officer: +2348000000002 / Kyc#2026")
if kyc_officer is None:
    kyc_officer = User.objects.filter(roles__role__code="KYC_OFFICER").first()

# -- Agent ------------------------------------------------------------------
agent = Agent.objects.filter(user__phone="+2348000000100").first()
if agent is None and not User.objects.filter(phone="+2348000000100").exists():
    agent_user = User.objects.create_user(
        phone="+2348000000100",
        password="Agent#2026",
        first_name="Amina",
        last_name="Suleiman",
    )
    grant_role(agent_user, "AGENT")
    agent = agent_services.register_agent(
        user=agent_user,
        territory_code="KJ-A1",
        business_name="Amina Rural Services",
    )
    print("  agent: +2348000000100 / Agent#2026")

# -- Cooperative ------------------------------------------------------------
org, _ = Organization.objects.get_or_create(
    name="Zaria Maize Growers Cooperative",
    defaults={
        "type": Organization.Type.COOPERATIVE,
        "state": "Kaduna",
        "lga": "Zaria",
        "registration_number": "KD/2026/COOP/0142",
    },
)
coop, _ = Cooperative.objects.get_or_create(organization=org)

# -- Customers ----------------------------------------------------------------
demo_customers = [
    ("+2348012345001", "Adaeze", "Okonkwo", "TRADER", "Anambra", "Awka South", "VERIFIED"),
    ("+2348012345002", "Ibrahim", "Musa", "FARMER", "Kaduna", "Zaria", "PENDING"),
    ("+2348012345003", "Funmilayo", "Adeyemi", "ARTISAN", "Oyo", "Ibadan North", "NOT_STARTED"),
]
for phone, first, last, occupation, state, lga, kyc_state in demo_customers:
    user = User.objects.filter(phone=phone).first()
    if user is None:
        user = User.objects.create_user(
            phone=phone,
            password="Customer#2026",
            first_name=first,
            last_name=last,
        )
        grant_role(user, "CUSTOMER")
        customer = customer_services.create_customer_profile(
            user=user,
            first_name=first,
            last_name=last,
            occupation=occupation,
            state=state,
            lga=lga,
            community="Central",
        )
        profile = kyc_services.get_or_create_profile(customer)
        if kyc_state == "VERIFIED":
            profile = kyc_services.submit_kyc(
                customer, doc_type="NIN", id_number="12345678901"
            )
            kyc_services.review_kyc(
                profile,
                reviewer=kyc_officer,
                decision="APPROVED",
                reason="Test deployment verification",
                new_level="STANDARD",
            )
        elif kyc_state == "PENDING":
            kyc_services.submit_kyc(
                customer, doc_type="BVN", id_number="22233344455"
            )
        print(f"  customer: {phone} / Customer#2026 (kyc={kyc_state})")

# -- Farmer profile for the farmer customer ----------------------------------
farmer_cust = Customer.objects.filter(user__phone="+2348012345002").first()
if farmer_cust and FarmerProfile.objects.filter(customer=farmer_cust).first() is None:
    farmer = FarmerProfile.objects.create(
        customer=farmer_cust,
        years_of_experience=12,
        primary_crops=["MAIZE", "SORGHUM"],
        cooperative=coop,
        farming_type="SMALLHOLDER",
    )
    Farm.objects.create(
        farmer=farmer,
        name="Family plot",
        state="Kaduna",
        lga="Zaria",
        community="Kufena",
        size_hectares=Decimal("2.50"),
        ownership="OWNED",
    )
    CooperativeMember.objects.get_or_create(
        cooperative=coop, customer=farmer_cust, defaults={"role": "MEMBER"}
    )

# -- Savings plans (unfunded: fund them via agent collection / Paystack) ------
start = date.today()
plan_specs = [
    ("+2348012345001", "AJO_DAILY", "DAILY", 500, 30),
    ("+2348012345002", "AJO_WEEKLY", "WEEKLY", 2000, 60),
]
for phone, product, frequency, amount, days in plan_specs:
    customer = Customer.objects.filter(user__phone=phone).first()
    if customer is None or SavingsPlan.objects.filter(
        customer=customer, product__code=product
    ).exists():
        continue
    plan = savings_services.create_savings_plan(
        customer=customer,
        product_code=product,
        amount=Decimal(amount),
        frequency=frequency,
        start_date=start - timedelta(days=days),
        end_date=start + timedelta(days=days),
        allow_past_start=True,
    )
    print(f"  savings plan {plan.reference} ({product}, unfunded)")

print("Bootstrap complete.")
print("Logins are the documented demo accounts (see README).")

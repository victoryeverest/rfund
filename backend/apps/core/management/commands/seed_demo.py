"""Development seed command (spec §84, §175).

python manage.py seed_demo

Creates admin, staff, customers, agents, a cooperative, products,
and sample transactions — no real personal information.
REFUSES to run in production (no override exists).
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger("rfund.seed")


class Command(BaseCommand):
    help = "Seed the database with safe demo data. Refuses in production."

    def handle(self, *args, **options):
        if settings.DJANGO_ENV == "production" or not settings.ALLOW_SEED_IN_PRODUCTION:
            if settings.DJANGO_ENV == "production":
                raise CommandError(
                    "seed_demo refuses to run in production. This is intentional "
                    "and there is no override."
                )

        from apps.accounts.models import Role, User
        from apps.accounts.services import bootstrap_rbac, grant_role
        from apps.agents.models import AgentTerritory
        from apps.agents import services as agent_services
        from apps.agriculture.models import Crop
        from apps.cooperatives.models import Cooperative, CooperativeMember
        from apps.customers import services as customer_services
        from apps.customers.models import Customer
        from apps.farmers.models import FarmerProfile, Farm
        from apps.fraud.services import ensure_default_rules
        from apps.identity import services as kyc_services
        from apps.identity.models import KYCProfile
        from apps.ledger.services import ensure_core_accounts
        from apps.loans import services as loan_services
        from apps.notifications.services import ensure_default_templates
        from apps.organizations.models import Organization
        from apps.risk.services import ensure_default_rules as ensure_risk_rules
        from apps.savings import services as savings_services
        from apps.savings.models import SavingsPlan
        from apps.settlements.services import run_reconciliation

        self.stdout.write("Seeding RBAC ...")
        bootstrap_rbac()
        ensure_core_accounts()
        ensure_risk_rules()
        ensure_default_rules()  # fraud rules
        ensure_default_templates()
        savings_services.ensure_default_products()
        loan_services.ensure_default_products()

        # -- Territories & crops -------------------------------------------------
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
            self.stdout.write("  super admin: +2348000000000 / Admin#2026")

        # -- Finance officer ---------------------------------------------------------
        if not User.objects.filter(phone="+2348000000001").exists():
            finance = User.objects.create_user(
                phone="+2348000000001",
                password="Finance#2026",
                first_name="Finance",
                last_name="Officer",
                email="finance@rfund.example",
            )
            grant_role(finance, "FINANCE_OFFICER")
        # -- KYC officer
        if not User.objects.filter(phone="+2348000000002").exists():
            kyc_user = User.objects.create_user(
                phone="+2348000000002",
                password="Kyc#2026",
                first_name="KYC",
                last_name="Officer",
                email="kyc@rfund.example",
            )
            grant_role(kyc_user, "KYC_OFFICER")
        # -- Loan officer
        if not User.objects.filter(phone="+2348000000003").exists():
            loan_user = User.objects.create_user(
                phone="+2348000000003",
                password="Loan#2026",
                first_name="Loan",
                last_name="Officer",
                email="loans@rfund.example",
            )
            grant_role(loan_user, "LOAN_OFFICER")

        # -- Agent -----------------------------------------------------------------
        if not User.objects.filter(phone="+2348000000100").exists():
            agent_user = User.objects.create_user(
                phone="+2348000000100",
                password="Agent#2026",
                first_name="Amina",
                last_name="Suleiman",
            )
            grant_role(agent_user, "AGENT")
            agent_services.register_agent(
                user=agent_user,
                territory_code="KJ-A1",
                business_name="Amina Rural Services",
            )
            self.stdout.write("  agent: +2348000000100 / Agent#2026")

        # -- Cooperative -----------------------------------------------------------
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

        # -- Customers ---------------------------------------------------------------
        demo_customers = [
            ("+2348012345001", "Adaeze", "Okonkwo", "TRADER", "Anambra", "Awka South", "VERIFIED"),
            ("+2348012345002", "Ibrahim", "Musa", "FARMER", "Kaduna", "Zaria", "VERIFIED"),
            ("+2348012345003", "Funmilayo", "Adeyemi", "ARTISAN", "Oyo", "Ibadan North", "PENDING"),
            ("+2348012345004", "Chinedu", "Eze", "FARMER", "Enugu", "Nsukka", "VERIFIED"),
            ("+2348012345005", "Hauwa", "Garba", "TRADER", "Kano", "Dawakin Tofa", "NOT_STARTED"),
        ]
        customers = []
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
                        reviewer=User.objects.filter(roles__role__code="KYC_OFFICER").first(),
                        decision="APPROVED",
                        reason="Seeded demo verification",
                        new_level="STANDARD",
                    )
                elif kyc_state == "PENDING":
                    kyc_services.submit_kyc(
                        customer, doc_type="BVN", id_number="22233344455"
                    )
                customers.append(customer)
            else:
                customers.append(Customer.objects.filter(user=user).first())

        # Farmer profiles
        farmer2 = FarmerProfile.objects.filter(customer=customers[1]).first()
        if farmer2 is None:
            farmer2 = FarmerProfile.objects.create(
                customer=customers[1],
                years_of_experience=12,
                primary_crops=["MAIZE", "SORGHUM"],
                cooperative=coop,
                farming_type="SMALLHOLDER",
            )
            Farm.objects.create(
                farmer=farmer2,
                name="Family plot",
                state="Kaduna",
                lga="Zaria",
                community="Kufena",
                size_hectares=Decimal("2.50"),
                ownership="OWNED",
            )
            CooperativeMember.objects.get_or_create(
                cooperative=coop, customer=customers[1], defaults={"role": "MEMBER"}
            )

        # -- Savings plans with contributions ------------------------------------------
        from apps.payments import services as payment_services

        start = date.today()
        plan_specs = [
            (customers[0], "AJO_DAILY", "DAILY", 500, 30),
            (customers[1], "AJO_WEEKLY", "WEEKLY", 2000, 60),
            (customers[3], "AJO_MONTHLY", "MONTHLY", 10000, 180),
        ]
        for customer, product, frequency, amount, days in plan_specs:
            if SavingsPlan.objects.filter(customer=customer, product__code=product).exists():
                continue
            from datetime import timedelta

            plan = savings_services.create_savings_plan(
                customer=customer,
                product_code=product,
                amount=Decimal(amount),
                frequency=frequency,
                start_date=start - timedelta(days=days),
                end_date=start + timedelta(days=days),
                allow_past_start=True,
            )
            # Simulate a settled payment into the plan
            payment, _url = payment_services.initialize_payment(
                customer=customer,
                purpose="SAVINGS_CONTRIBUTION",
                amount=Decimal(amount),
                target={"plan_id": str(plan.pk)},
            )
            from apps.payments.models import PaymentProviderEvent, PaymentWebhookEvent
            from apps.payments.services import process_webhook_event

            provider = payment.provider
            if provider == "local":
                from integrations.payments.base import get_payment_provider

                local = get_payment_provider("local")
                payload = local.mark_success(payment.provider_reference)
                event = PaymentWebhookEvent.objects.create(
                    provider="local",
                    event_id=f"seed-{payment.reference}",
                    event_type="charge.success",
                    payload=payload,
                    signature_valid=True,
                )
                process_webhook_event(event)
            self.stdout.write(f"  savings plan {plan.reference} funded")

        # -- A loan application in review ---------------------------------------------
        from apps.loans.models import LoanApplication

        if not LoanApplication.objects.filter(customer=customers[0]).exists():
            loan_services.create_loan_application(
                customer=customers[0],
                product_code="TRADER",
                amount=Decimal(50000),
                term_months=6,
                purpose="Restock the shop before the market season",
                business_info={"business_name": "Adaeze Provisions", "business_type": "RETAIL"},
            )
            self.stdout.write("  loan application created")

        # -- Reconciliation baseline ------------------------------------------------------
        run_reconciliation(provider="local")

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write(
            "Demo logins (phone / password):\n"
            "  admin    +2348000000000 / Admin#2026\n"
            "  finance  +2348000000001 / Finance#2026\n"
            "  kyc      +2348000000002 / Kyc#2026\n"
            "  loans    +2348000000003 / Loan#2026\n"
            "  agent    +2348000000100 / Agent#2026\n"
            "  customer +2348012345001 / Customer#2026 (and ...5002-5005)"
        )

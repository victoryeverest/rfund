import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
django.setup()
from apps.customers.models import Customer
from apps.savings.models import SavingsPlan
from apps.ledger.models import LedgerAccount

c = Customer.objects.filter(user__phone='+2348012345001').first()
print('customer:', c.full_name if c else None)
for p in SavingsPlan.objects.filter(customer=c):
    items = p.schedule_items.all()
    paid = sum(1 for i in items if i.amount_paid > 0)
    print('plan:', p.reference, p.status, 'contributed:', p.total_contributed, f'paid_items: {paid}/{len(items)}')
for a in LedgerAccount.objects.filter(holder_customer=c):
    print('ledger acct:', a.code, a.name, 'balance:', a.balance)
print('--- all accounts holding nothing? sample:')
for a in LedgerAccount.objects.filter(code__contains='SAV')[:10]:
    print('sav acct:', a.code, 'holder:', a.holder_customer_id, 'balance:', a.balance)

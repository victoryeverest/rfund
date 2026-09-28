import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
django.setup()
from django.db import connection

with connection.cursor() as cur:
    cur.execute("SELECT datname, pid, state, wait_event_type, wait_event, now()-query_start AS age, left(query, 60) FROM pg_stat_activity WHERE datname IS NOT NULL ORDER BY query_start")
    for row in cur.fetchall():
        print(row)

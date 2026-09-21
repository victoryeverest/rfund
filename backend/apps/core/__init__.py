"""Core domain primitives shared by every RFUND app.

Contains no business logic itself: base models, money handling, domain
errors, reference generation, cursor pagination, clock helpers.
"""

default_app_config = "apps.core.apps.CoreConfig"

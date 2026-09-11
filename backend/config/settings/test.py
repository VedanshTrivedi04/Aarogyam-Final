"""
config/settings/test.py — Isolated settings for the automated test suite.

The dev database is a remote Neon instance, so tests run against local SQLite
instead. Usage:

    python manage.py test tests --settings=config.settings.test
"""
from .development import *  # noqa: F401,F403

# ai_engine's models use Postgres schema-qualified table names
# ('"ai_engine"."risk_scores"'), which SQLite cannot create. Nothing outside
# that app holds foreign keys into it, so it is dropped for tests.
INSTALLED_APPS = [a for a in INSTALLED_APPS if a != 'apps.ai_engine']  # noqa: F405

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
}

CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


class DisableMigrations:
    """
    Build tables straight from the current models. Some migrations carry raw
    Postgres DDL (CREATE SCHEMA) that SQLite cannot execute.
    """
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

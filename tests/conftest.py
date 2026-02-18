"""Pytest configuration for django-mongodb-extensions tests."""

import django
from django.conf import settings


def pytest_configure():
    """Configure Django settings for tests."""
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django_mongodb_backend",
                    "NAME": "test_db",
                }
            },
            # Note: We use standard Django apps (contenttypes, auth) instead of
            # MongoDB-specific versions because they're only needed for test
            # infrastructure (e.g., debug toolbar dependencies) and don't need
            # to be MongoDB-specific. The MQL panel tests focus on testing the
            # panel itself, not the underlying Django apps.
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "debug_toolbar",
                "django_mongodb_extensions",
            ],
            SECRET_KEY="test-secret-key",
            USE_TZ=True,
            # Debug toolbar settings
            DEBUG_TOOLBAR_PANELS=[
                "django_mongodb_extensions.debug_toolbar.panels.MQLPanel",
            ],
            # Custom setting for MQL panel
            DJDT_MQL_MAX_SELECT_RESULTS=100,
        )
        django.setup()

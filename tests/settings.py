"""Django settings for running tests."""

import os

SECRET_KEY = "test-secret-key-for-django-mongodb-extensions"

DEBUG = True

INSTALLED_APPS = [
    "tests.apps.MongoAuthConfig",
    "tests.apps.MongoContentTypesConfig",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "debug_toolbar",
    "django_mongodb_extensions",
]

DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "NAME": "test_django_mongodb_extensions",
        "HOST": os.environ.get(
            "MONGODB_URI", "mongodb://localhost:27017/?replicaSet=test-rs"
        ),
    }
}

# Database routers
DATABASE_ROUTERS = ["django_mongodb_backend.routers.MongoRouter"]

# Minimal middleware for tests
MIDDLEWARE = []

# Required for Django
ROOT_URLCONF = "tests.urls"

USE_TZ = True

# Required for debug_toolbar
STATIC_URL = "/static/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"

# Disable migrations for tests
MIGRATION_MODULES = {
    "auth": None,
    "contenttypes": None,
    "sessions": None,
}

# Debug toolbar panels - include MQLPanel for testing
DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.history.HistoryPanel",
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "django_mongodb_extensions.debug_toolbar.panels.mql.panel.MQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.alerts.AlertsPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]

# Templates configuration for debug_toolbar
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

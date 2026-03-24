# django-mongodb-extensions

Extensions for Django MongoDB Backend

## Extensions

### MQL Panel for Django Debug Toolbar

The first extension is the **MQL Panel** for
[django-debug-toolbar](https://github.com/jazzband/django-debug-toolbar).
This panel provides detailed insights into MongoDB queries executed during a
request, similar to how the SQL panel works for relational databases.

**Features:**

- View all MongoDB queries (MQL) executed during a request
- See query execution time and identify slow queries
- Re-execute read operations (aggregate) directly from the toolbar
- Explain query execution plans
- Color-coded query grouping for easy identification
- Detailed query statistics and performance metrics

## Installation

### Requirements

- [django-mongodb-backend](https://github.com/mongodb-labs/django-mongodb-backend)
- [django-debug-toolbar](https://github.com/jazzband/django-debug-toolbar)

First, install and configure django-debug-toolbar by following their
[installation instructions](https://django-debug-toolbar.readthedocs.io/en/latest/installation.html).

### Install the Package

```bash
pip install django-mongodb-extensions
```

### Configure the MQL Panel

1. **Add to `INSTALLED_APPS`** in your Django settings:

```python
INSTALLED_APPS = [
    # ...
    'debug_toolbar',
    'django_mongodb_extensions',
    # ...
]
```

2. **Add the MQL Panel** to your debug toolbar configuration:

```python
DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.history.HistoryPanel',
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    # Add this:
    'django_mongodb_extensions.debug_toolbar.panels.mql.panel.MQLPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
]
```

3. **Optional:** Configure settings.

```python
# Maximum number of documents to return when re-executing select
# queries (default is 100).
DJDT_MQL_MAX_SELECT_RESULTS = 25

# Queries slower than this threshold (in milliseconds) are highlighted
# in the debug toolbar (default is 500 ms).
DJDT_MQL_WARNING_THRESHOLD = 1000
```

## License

See [LICENSE](LICENSE) file for details.

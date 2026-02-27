# Django MongoDB Extensions

A collection of extensions for Django when using MongoDB, inspired by
[django-extensions](https://github.com/django-extensions/django-extensions).

**Note:** This library does not require django-debug-toolbar, but you will
need it to use the MQL Panel extension.

## Extensions

### MQL Panel for Django Debug Toolbar

The first extension is the **MQL Panel** for
[django-debug-toolbar](https://github.com/jazzband/django-debug-toolbar).
This panel provides detailed insights into MongoDB queries executed during a
request, similar to how the SQL panel works for relational databases.

**Features:**
- View all MongoDB queries (MQL) executed during a request
- See query execution time and identify slow queries
- Re-execute read operations (find, aggregate, etc.) directly from the toolbar
- Explain query execution plans
- Color-coded query grouping for easy identification
- Detailed query statistics and performance metrics

## Installation

### Requirements

- [django-mongodb-backend](https://github.com/mongodb-labs/django-mongodb-backend)
- [django-debug-toolbar](https://github.com/jazzband/django-debug-toolbar)

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
    # Add this
    'django_mongodb_extensions.debug_toolbar.panels.MQLPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
]
```

3. **Optional: Configure maximum select results** (default is 100):

```python
# Maximum number of documents to return when re-executing select
# queries
DJDT_MQL_MAX_SELECT_RESULTS = 25
```

### Usage

Once installed and configured, the MQL Panel will automatically appear in
your Django Debug Toolbar. It will display:

- **Query list**: All MongoDB operations executed during the request
- **Execution time**: Time taken for each query
- **Query details**: Collection name, operation type, and arguments
- **Explain button**: Click to see the query execution plan
- **Select button**: Re-execute read operations to see results

## Development

### Running Tests

This project uses Django's built-in test framework. To run tests:

```bash
pip install -e '.[test]'
django-admin test --settings=tests.settings
```

## License

See [LICENSE](LICENSE) file for details.

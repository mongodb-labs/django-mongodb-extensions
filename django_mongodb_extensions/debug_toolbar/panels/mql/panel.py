from django.db import connections
from django.utils.translation import gettext_lazy as _, ngettext

from debug_toolbar.panels.sql.panel import SQLPanel
from django_mongodb_extensions.debug_toolbar.panels.mql.tracking import (
    patch_get_collection,
)


class MQLPanel(SQLPanel):
    """
    Panel that displays information about the MQL queries run while processing
    the request.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sql_time = 0
        self._queries = []
        self._databases = {}

    # Implement Panel API

    nav_title = _("MQL")
    template = "debug_toolbar/panels/mql.html"

    @property
    def nav_subtitle(self):
        query_count = len(self._queries)
        return ngettext(
            "%(query_count)d query in %(sql_time).2fms",
            "%(query_count)d queries in %(sql_time).2fms",
            query_count,
        ) % {
            "query_count": query_count,
            "sql_time": self._sql_time,
        }

    @property
    def title(self):
        count = len(self._databases)
        return ngettext(
            "MQL queries from %(count)d connection",
            "MQL queries from %(count)d connections",
            count,
        ) % {"count": count}

    def enable_instrumentation(self):
        # This is thread-safe because database connections are thread-local.
        for connection in connections.all():
            patch_get_collection(connection)
            connection._djdt_logger = self

    def disable_instrumentation(self):
        for connection in connections.all():
            connection._djdt_logger = None

    def generate_stats(self, request, response):
        self.record_stats(
            {
                "queries": self._queries,
            }
        )

from collections import defaultdict

from django.db import connections
from django.urls import path
from django.utils.translation import gettext_lazy as _, ngettext

from debug_toolbar.panels import Panel
from debug_toolbar.panels.sql import views
from django_mongodb_extensions.debug_toolbar.panels.mql.tracking import (
    patch_get_collection,
)


def _similar_query_key(query):
    return query["raw_sql"]


def _duplicate_query_key(query):
    raw_params = () if query["raw_params"] is None else tuple(query["raw_params"])
    # repr() avoids problems because of unhashable types
    # (e.g. lists) when used as dictionary keys.
    # https://github.com/django-commons/django-debug-toolbar/issues/1091
    return (query["raw_sql"], repr(raw_params))


def _process_query_groups(query_groups, databases, colors, name):
    counts = defaultdict(int)
    for (alias, _key), query_group in query_groups.items():
        count = len(query_group)
        # Queries are similar / duplicates only if there are at least 2 of them.
        if count > 1:
            color = next(colors)
            for query in query_group:
                query[f"{name}_count"] = count
                query[f"{name}_color"] = color
            counts[alias] += count
    for alias, db_info in databases.items():
        db_info[f"{name}_count"] = counts[alias]


class MQLPanel(Panel):
    """
    Panel that displays information about the MQL queries run while processing
    the request.
    """

    # Implement the Panel API

    nav_title = _("MQL")

    @property
    def nav_subtitle(self):
        query_count = 1
        return ngettext(
            "%(query_count)d query in %(sql_time).2fms",
            "%(query_count)d queries in %(sql_time).2fms",
            query_count,
        ) % {
            "query_count": query_count,
            "sql_time": 1,
        }

    @property
    def title(self):
        count = 1
        return ngettext(
            "MQL queries from %(count)d connection",
            "MQL queries from %(count)d connections",
            count,
        ) % {"count": count}

    template = "debug_toolbar/panels/mql.html"

    @classmethod
    def get_urls(cls):
        return [
            path("sql_select/", views.sql_select, name="sql_select"),
            path("sql_explain/", views.sql_explain, name="sql_explain"),
            path("sql_profile/", views.sql_profile, name="sql_profile"),
        ]

    def enable_instrumentation(self):
        # This is thread-safe because database connections are thread-local.
        for connection in connections.all():
            patch_get_collection(connection)
            connection._djdt_panel = self

    def disable_instrumentation(self):
        for connection in connections.all():
            connection._djdt_panel = None

    def generate_stats(self, request, response):
        self.record_stats(
            {
                "databases": [],
                "queries": [],
                "sql_time": [],
            }
        )

    def generate_server_timing(self, request, response):
        stats = self.get_stats()
        title = "MQL {} queries".format(len(stats.get("queries", [])))
        value = stats.get("sql_time", 0)
        self.record_server_timing("sql_time", title, value)

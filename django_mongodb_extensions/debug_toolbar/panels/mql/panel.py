import uuid
from collections import defaultdict

from django.db import connections
from django.db.backends.signals import connection_created
from django.template.loader import render_to_string
from django.urls import path
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _, ngettext

from debug_toolbar.forms import SignedDataForm
from debug_toolbar.panels.sql.forms import SQLSelectForm
from debug_toolbar.panels.sql.panel import SQLPanel
from debug_toolbar.panels.sql.utils import contrasting_color_generator
from debug_toolbar.utils import render_stacktrace
from django_mongodb_extensions.debug_toolbar.panels.mql.utils import (
    MQL_PANEL_ID,
    MQL_READ_OPERATIONS,
    get_mql_warning_threshold,
    patch_get_collection,
    patch_new_connection,
)
from django_mongodb_extensions.debug_toolbar.panels.mql import views


# Use dispatch_uid to ensure the signal handler is only registered once,
# even if the module is imported multiple times (e.g., during autoreload or testing).
connection_created.connect(
    patch_new_connection,
    dispatch_uid="django_mongodb_extensions_mql_panel_patch_new_connection",
)


class MQLPanel(SQLPanel):
    panel_id = MQL_PANEL_ID

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mql_time = 0
        self._queries = []
        self._databases = {}

    def record(self, **kwargs):
        kwargs["djdt_query_id"] = uuid.uuid4().hex
        self._queries.append(kwargs)
        alias = kwargs["alias"]
        if alias not in self._databases:
            self._databases[alias] = {
                "time_spent": kwargs["duration"],
                "num_queries": 1,
            }
        else:
            self._databases[alias]["time_spent"] += kwargs["duration"]
            self._databases[alias]["num_queries"] += 1
        self._mql_time += kwargs["duration"]

    # Implement Panel API

    nav_title = _("MQL")
    template = "debug_toolbar/panels/mql.html"

    @classmethod
    def get_urls(cls):
        return [
            path("mql_select/", views.mql_select, name="mql_select"),
            path("mql_explain/", views.mql_explain, name="mql_explain"),
        ]

    @property
    def nav_subtitle(self):
        stats = self.get_stats()
        query_count = len(stats.get("queries", []))
        return ngettext(
            "%(query_count)d query in %(mql_time).2fms",
            "%(query_count)d queries in %(mql_time).2fms",
            query_count,
        ) % {
            "query_count": query_count,
            "mql_time": stats.get("mql_time"),
        }

    @property
    def title(self):
        stats = self.get_stats()
        databases = stats.get("databases", {}) if stats else {}
        count = len(databases)
        return ngettext(
            "MQL queries from %(count)d connection",
            "MQL queries from %(count)d connections",
            count,
        ) % {"count": count}

    def enable_instrumentation(self):
        # Only patch MongoDB connections (those with get_collection method).
        # This allows the panel to work in multi-database setups with
        # both MongoDB and relational databases.
        for connection in connections.all():
            if hasattr(connection, "get_collection"):
                patch_get_collection(connection)
                connection._djdt_logger = self

    def disable_instrumentation(self):
        for connection in connections.all():
            if hasattr(connection, "_djdt_logger"):
                connection._djdt_logger = None

    @staticmethod
    def _hex_to_rgb(hex_color):
        """Convert a hex color string to RGB values.

        Used to convert hex colors from contrasting_color_generator() to RGB
        format for display in the debug toolbar UI.
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            # Return a default gray color if invalid
            return [128, 128, 128]

        try:
            # Convert hex to RGB
            return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            return [128, 128, 128]

    @staticmethod
    def _is_read_operation(operation):
        """Check if a MongoDB operation is a read operation.

        Read operations (like SQL SELECT) retrieve data without modifying it.
        This determines whether the Sel and Expl buttons are shown in the UI
        for re-executing queries.
        """
        return operation in MQL_READ_OPERATIONS

    @staticmethod
    def _query_key_similar(query):
        """Generate a key for grouping similar queries.

        Similar queries have the same collection and operation, regardless of arguments.
        Returns a template like "db.collection.operation()" for grouping.
        """
        collection = query["mql_collection"]
        operation = query["mql_operation"]
        return f"db.{collection}.{operation}()"

    @staticmethod
    def _process_query_groups(query_groups, databases, colors, name):
        """Process grouped queries to add color coding and count metadata for display.

        For each group with 2+ queries, this function:
        - Assigns a unique color to visually group them in the UI
        - Adds {name}_count and {name}_color attributes to each query dict
        - Updates database-level counts in the databases dict

        Called twice in generate_stats():
        - Once with similar_query_groups and name="similar" to highlight queries with
          the same operation but different parameters
        - Once with duplicate_query_groups and name="duplicate" to highlight identical
          queries (same operation and parameters)
        """
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

    def generate_stats(self, request, response):
        similar_query_groups = defaultdict(list)
        duplicate_query_groups = defaultdict(list)

        if self._queries:
            mql_warning_threshold = get_mql_warning_threshold()

            db_colors = contrasting_color_generator()
            for db in self._databases.values():
                hex_color = next(db_colors)
                db["rgb_color"] = self._hex_to_rgb(hex_color)

            width_ratio_tally = 0

            for query in self._queries:
                alias = query["alias"]

                try:
                    sim_key = self._query_key_similar(query)
                    similar_query_groups[(alias, sim_key)].append(query)
                except KeyError:
                    pass

                dup_key = query.get("mql", "")
                duplicate_query_groups[(alias, dup_key)].append(query)

                query["is_slow"] = query["duration"] > mql_warning_threshold

                operation = query.get("mql_operation", "")
                # Only show Sel/Expl buttons if it's a read operation AND
                # the args were successfully serialized (mql_args_json is not None).
                args_json = query.get("mql_args_json")
                query["is_select"] = (
                    self._is_read_operation(operation) and args_json is not None
                )

                query["rgb_color"] = self._databases[alias]["rgb_color"]
                try:
                    query["width_ratio"] = (query["duration"] / self._mql_time) * 100
                except ZeroDivisionError:
                    query["width_ratio"] = 0
                query["start_offset"] = width_ratio_tally
                query["end_offset"] = query["width_ratio"] + query["start_offset"]
                width_ratio_tally += query["width_ratio"]

        group_colors = contrasting_color_generator()
        self._process_query_groups(
            similar_query_groups, self._databases, group_colors, "similar"
        )
        self._process_query_groups(
            duplicate_query_groups, self._databases, group_colors, "duplicate"
        )

        self.record_stats(
            {
                "databases": sorted(
                    self._databases.items(), key=lambda x: -x[1]["time_spent"]
                ),
                "queries": self._queries,
                "mql_time": self._mql_time,
            }
        )

    def generate_server_timing(self, request, response):
        stats = self.get_stats()
        title = f"MQL {len(stats.get('queries', []))} queries"
        value = stats.get("mql_time", 0)
        self.record_server_timing("mql_time", title, value)

    @property
    def has_content(self):
        return bool(self._queries)

    @cached_property
    def content(self):
        stats = self.get_stats()
        colors = contrasting_color_generator()
        trace_colors = defaultdict(lambda: next(colors))
        for query in stats.get("queries", []):
            query["mql"] = query.get("mql", "")
            query["params"] = True
            query["form"] = SignedDataForm(
                auto_id=None,
                initial=SQLSelectForm(
                    initial={
                        "djdt_query_id": query["djdt_query_id"],
                        "request_id": self.toolbar.request_id,
                    }
                ).initial,
            )
            query["stacktrace"] = render_stacktrace(query["stacktrace"])
            query["trace_color"] = trace_colors[query["stacktrace"]]

        return render_to_string(self.template, stats)

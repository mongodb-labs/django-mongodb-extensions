"""Utility functions and constants for MQL panel."""

import pprint
import types
import weakref
from collections import defaultdict

from bson import json_util
from debug_toolbar.utils import get_stack_trace
from django.conf import settings
from django_mongodb_backend.utils import OperationDebugWrapper


MQL_PANEL_ID = "MQLPanel"

# Default maximum number of documents to return when re-executing queries.
# This limit prevents performance issues when displaying large result sets in the
# debug toolbar's Sel view.
#
# To customize this value, add the following setting to your Django settings file:
#
#     DJDT_MQL_MAX_SELECT_RESULTS = 200  # or any other integer value
#
# The setting is read by the get_max_select_results() function below.
DEFAULT_MAX_SELECT_RESULTS = 100

# Queries slower than this threshold (in milliseconds) are highlighted in the
# debug toolbar. Customize via DJDT_MQL_WARNING_THRESHOLD in Django settings.
DEFAULT_MQL_WARNING_THRESHOLD = 500


# Read operations used by django-mongodb-backend.
# These are the only MongoDB read operations that django-mongodb-backend actually
# uses, so they're the only ones we need to support in the debug toolbar.
MQL_READ_OPERATIONS = {
    "find",
    "aggregate",
    "count_documents",
}

# Track which connections have been patched to avoid double-patching
# Use WeakSet to automatically clean up references to closed connections
_patched_connections = weakref.WeakSet()


class QueryParts:
    """Structured container for parsed query components."""

    def __init__(
        self,
        query_dict,
        alias,
        mql_string,
        connection,
        db,
        collection,
        collection_name,
        operation,
        args_list,
    ):
        self.query_dict = query_dict
        self.alias = alias
        self.mql_string = mql_string
        self.connection = connection
        self.db = db
        self.collection = collection
        self.collection_name = collection_name
        self.operation = operation
        self.args_list = args_list


class DebugToolbarWrapper(OperationDebugWrapper):
    """
    A wrapper around pymongo Collection objects that logs queries for the
    debug toolbar.
    """

    def __init__(self, db, collection, logger):
        super().__init__(db, collection)
        self.logger = logger

    def log(self, op, duration, args, kwargs=None):
        args_str = ", ".join(repr(arg) for arg in args)
        operation = f"db.{self.collection_name}{op}({args_str})"
        try:
            args_json = json_util.dumps(list(args))
        except (TypeError, ValueError):
            args_json = None

        if self.logger:
            self.logger.record(
                alias=self.db.alias,
                mql=operation,
                duration=duration,
                stacktrace=get_stack_trace(),
                mql_collection=self.collection_name.strip("."),
                mql_operation=op.lstrip("."),
                mql_args_json=args_json,
            )


def convert_documents_to_table(documents):
    """Convert MongoDB documents to table format with columns. Used in the debug
    toolbar to display query results.
    """
    if not documents:
        return [], []

    # Collect all unique field names and build rows in a single pass
    all_fields = set()
    rows_data = []

    for doc in documents:
        all_fields.update(doc.keys())
        rows_data.append(doc)

    # Sort fields for consistent column ordering, with _id first if present
    headers = sorted(all_fields)
    if "_id" in headers:
        headers.remove("_id")
        headers.insert(0, "_id")

    # Convert each document to a row with values for each field
    rows = []
    for doc in rows_data:
        row = []
        for field in headers:
            value = doc.get(field)
            if value is not None:
                row.append(json_util.dumps(value))
            else:
                row.append("")
        rows.append(row)

    return rows, headers


def format_mql_query(query):
    """Format MQL query for display with pretty-printed arguments.

    Takes a query dictionary and formats it into a readable MQL string
    with pretty-printed arguments.

    Called by:
    - mql_explain() view to format queries for display in explain output
    - mql_select() view to format queries for display in select output

    Args:
        query: Query dictionary containing mql, mql_collection, mql_operation,
               and mql_args_json fields

    Returns:
        str: Formatted MQL query string, or the original mql string if formatting fails
    """
    mql_string = query.get("mql", "")
    try:
        collection_name, operation, args_list = parse_query_args(query)
        if args_list:
            # For single argument operations, format the argument directly
            args_formatted = pprint.pformat(
                args_list[0] if len(args_list) == 1 else args_list,
                width=80,
                compact=False,
                indent=2,
            )
        else:
            args_formatted = ""

        # Reconstruct the MQL string with pretty-printed arguments
        return f"db.{collection_name}.{operation}(\n{args_formatted}\n)"
    except Exception:
        # parse_query_args raises ValueError; pprint.pformat can raise anything
        # if a document value's __repr__ is broken, so we keep the broad catch.
        return mql_string


def get_max_select_results():
    """Get the maximum number of results to return when re-executing queries.

    Returns the value from Django settings DJDT_MQL_MAX_SELECT_RESULTS if set,
    otherwise returns the default value.
    """
    return getattr(settings, "DJDT_MQL_MAX_SELECT_RESULTS", DEFAULT_MAX_SELECT_RESULTS)


def get_mql_warning_threshold():
    """Get the slow-query warning threshold in milliseconds.

    Returns the value from Django settings DJDT_MQL_WARNING_THRESHOLD if set,
    otherwise returns the default value.
    """
    return getattr(
        settings, "DJDT_MQL_WARNING_THRESHOLD", DEFAULT_MQL_WARNING_THRESHOLD
    )


def hex_to_rgb(hex_color):
    """Convert a hex color string to RGB values."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        # Return a default gray color if invalid
        return [128, 128, 128]

    try:
        # Convert hex to RGB
        return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return [128, 128, 128]


def is_read_operation(operation):
    """
    Read operations (like SQL SELECT) retrieve data without modifying it.
    This is used for UI styling in the debug toolbar.

    Called by MQLPanel.generate_stats() in panel.py to set query["is_select"],
    which determines whether the Sel and Expl buttons are shown in the UI for
    re-executing queries.
    """
    return operation in MQL_READ_OPERATIONS


def parse_query_args(query_dict):
    """
    Parse structured query data into collection name, operation, and arguments.

    This function extracts and deserializes the MongoDB query components from
    the query dictionary that was logged by DebugToolbarWrapper.log().

    Called by:
    - MQLBaseForm._get_query_parts() in forms.py to prepare queries for
      re-execution in the Sel and Expl views.
    - format_mql_query() in views.py to pretty-print queries for display.
    """
    if not all(
        k in query_dict for k in ["mql_collection", "mql_operation", "mql_args_json"]
    ):
        raise ValueError(
            "Query does not have structured data. "
            "Only queries with structured data can be re-executed for security reasons. "
            "This query was likely logged before the security improvements were implemented."
        )

    collection_name = query_dict["mql_collection"]
    operation = query_dict["mql_operation"]
    args_json = query_dict["mql_args_json"]

    if not collection_name or not operation:
        raise ValueError("Missing required fields: collection_name or operation")

    if args_json is not None and args_json != "":
        try:
            args_list = json_util.loads(args_json)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to parse query arguments JSON: {str(e)}. "
                "The stored query data may be corrupted."
            )
        return collection_name, operation, args_list
    else:
        return collection_name, operation, []


def patch_get_collection(connection):
    """
    Patch the get_collection method of the connection to return a wrapped
    Collection object that logs queries for the debug toolbar.

    Save the original get_collection method so we can:
    - Call it to get the collection with any custom logic preserved.
    - Restore it later if needed (e.g., when disabling instrumentation).
    - Avoid infinite recursion when our patched method calls the original.
    """
    if connection in _patched_connections:
        return

    if not hasattr(connection, "_original_get_collection"):
        # Save the original method only if it hasn't been saved already
        connection._original_get_collection = connection.get_collection

    def get_collection(self, name, **kwargs):
        logger = getattr(self, "_djdt_logger", None)
        if logger:
            # Get the collection using the original method, then wrap it for logging
            collection = self._original_get_collection(name, **kwargs)
            return DebugToolbarWrapper(self, collection, logger)
        else:
            return self._original_get_collection(name, **kwargs)

    connection.get_collection = types.MethodType(get_collection, connection)

    # Only add to patched connections after successful patching
    _patched_connections.add(connection)


def patch_new_connection(sender, connection, **kwargs):
    """
    Signal handler for Django's connection_created signal that automatically
    patches new MongoDB connections for debug toolbar instrumentation.

    This function is connected to the connection_created signal in panel.py:
        connection_created.connect(patch_new_connection)

    When Django creates a new database connection, this handler is called. It checks
    if the connection is a MongoDB connection (by checking for 'database' and
    'get_collection' attributes) and if so, patches it to enable query logging.

    This ensures that all MongoDB connections are automatically instrumented without
    requiring manual patching, even for connections created after the panel is loaded.
    """
    if hasattr(connection, "database") and hasattr(connection, "get_collection"):
        patch_get_collection(connection)


def process_query_groups(query_groups, databases, colors, name):
    """
    Process grouped queries to add color coding and count metadata for display.

    This function is called by MQLPanel.generate_stats() in panel.py to annotate
    similar and duplicate queries with visual indicators (colors and counts) that
    are displayed in the debug toolbar UI.

    Called twice in generate_stats():
    - Once with similar_query_groups and name="similar" to highlight queries with
      the same operation but different parameters (e.g., db.users.find() with
      different filters)
    - Once with duplicate_query_groups and name="duplicate" to highlight identical
      queries (same operation and parameters)

    For each group with 2+ queries, this function:
    - Assigns a unique color to visually group them in the UI
    - Adds {name}_count and {name}_color attributes to each query dict
    - Updates database-level counts in the databases dict
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


def query_key_duplicate(query):
    """Generate a key for identifying duplicate queries.

    Duplicate queries are identical queries including their arguments.
    Uses the full mql string for exact matching.
    """
    return query.get("mql", "")


def query_key_similar(query):
    """Generate a key for grouping similar queries.

    Similar queries have the same collection and operation, regardless of arguments.
    Returns a template like "db.collection.operation()" for grouping.
    """
    collection = query["mql_collection"]
    operation = query["mql_operation"]
    return f"db.{collection}.{operation}()"

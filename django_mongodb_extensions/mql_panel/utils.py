import types
import weakref

from bson import json_util
from debug_toolbar.utils import get_stack_trace, get_template_info
from django.conf import settings
from django_mongodb_backend.utils import OperationDebugWrapper

DEFAULT_MAX_QUERY_RESULTS = 100
DEFAULT_MQL_WARNING_THRESHOLD = 500
_patched_connections = weakref.WeakSet()


class DebugToolbarWrapper(OperationDebugWrapper):
    """Wrapper around pymongo Collection objects that logs queries
    for display and re-execution."""

    def __init__(self, db, collection, logger):
        super().__init__(db, collection)
        self.logger = logger

    def log(self, op, duration, args, kwargs=None):
        args_str = ", ".join(repr(arg) for arg in args)
        operation = f"db.{self.collection_name}{op}({args_str})"
        args_json = json_util.dumps(list(args))
        if self.logger:
            self.logger.record(
                alias=self.db.alias,
                mql=operation,
                duration=duration,
                stacktrace=get_stack_trace(),
                template_info=get_template_info(),
                mql_collection=self.collection_name.strip("."),
                mql_operation=op.lstrip("."),
                mql_args_json=args_json,
            )


def format_mql_query(query):
    """Return a pretty-printed MQL query string."""
    collection_name, operation, args_list = parse_query_args(query)
    if args_list:
        args_formatted = json_util.dumps(
            args_list[0] if len(args_list) == 1 else args_list,
            indent=4,
        )
    else:
        args_formatted = ""
    return f"db.{collection_name}.{operation}(\n{args_formatted}\n)"


def get_max_query_results():
    """Get the maximum number of results to return when re-executing queries.

    Return the value from Django settings DJDT_MQL_MAX_QUERY_RESULTS if set,
    otherwise return the default value.
    """
    return getattr(settings, "DJDT_MQL_MAX_QUERY_RESULTS", DEFAULT_MAX_QUERY_RESULTS)


def get_mql_warning_threshold():
    """Get the slow-query warning threshold in milliseconds.

    Return the value from Django settings DJDT_MQL_WARNING_THRESHOLD if set,
    otherwise return the default value.
    """
    return getattr(
        settings, "DJDT_MQL_WARNING_THRESHOLD", DEFAULT_MQL_WARNING_THRESHOLD
    )


def parse_query_args(query_dict):
    """Extract and deserialize collection name, operation, and arguments."""
    collection_name = query_dict["mql_collection"]
    operation = query_dict["mql_operation"]
    args_json = query_dict["mql_args_json"]
    return collection_name, operation, json_util.loads(args_json)


def patch_get_collection(connection):
    """Patch get_collection to log queries via DebugToolbarWrapper."""
    if connection in _patched_connections:
        return
    if not hasattr(connection, "_original_get_collection"):
        connection._original_get_collection = connection.get_collection

    def get_collection(self, name, **kwargs):
        logger = getattr(self, "_djdt_logger", None)
        if logger:
            collection = self._original_get_collection(name, **kwargs)
            return DebugToolbarWrapper(self, collection, logger)
        else:
            return self._original_get_collection(name, **kwargs)

    connection.get_collection = types.MethodType(get_collection, connection)
    _patched_connections.add(connection)


def patch_new_connection(sender, connection, **kwargs):
    """Handle connection_created by patching new MongoDB connections."""
    if hasattr(connection, "database") and hasattr(connection, "get_collection"):
        patch_get_collection(connection)

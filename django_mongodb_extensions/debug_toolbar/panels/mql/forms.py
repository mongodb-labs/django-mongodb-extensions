import json

from bson import json_util
from debug_toolbar.panels.sql.forms import SQLSelectForm
from debug_toolbar.toolbar import DebugToolbar
from django import forms
from django.core.exceptions import ValidationError
from django.db import connections
from django.utils.translation import gettext_lazy as _
from pymongo import errors as pymongo_errors

from django_mongodb_extensions.debug_toolbar.panels.mql.utils import (
    MQL_PANEL_ID,
    QueryParts,
    get_max_select_results,
    parse_query_args,
)


class MQLBaseForm(SQLSelectForm):
    def clean(self):
        # Explicitly call forms.Form.clean() to bypass SQLSelectForm.clean()
        # which has SQL-specific validation not needed for MQL queries.
        cleaned_data = forms.Form.clean(self)
        request_id = cleaned_data.get("request_id")
        djdt_query_id = cleaned_data.get("djdt_query_id")
        if not request_id:
            raise ValidationError(_("Missing request ID."))
        if not djdt_query_id:
            raise ValidationError(_("Missing query ID."))
        toolbar = DebugToolbar.fetch(request_id, panel_id=MQL_PANEL_ID)
        if toolbar is None:
            raise ValidationError(_("Data for this panel isn't available anymore."))
        panel = toolbar.get_panel_by_id(MQL_PANEL_ID)
        stats = panel.get_stats()
        if not stats or "queries" not in stats:
            raise ValidationError(_("Query data is not available."))
        query = next(
            (
                _query
                for _query in stats["queries"]
                if isinstance(_query, dict)
                and _query.get("djdt_query_id") == djdt_query_id
            ),
            None,
        )
        if not query:
            raise ValidationError(_("Invalid query ID."))
        if not all(key in query for key in ["alias", "mql"]):
            raise ValidationError(_("Query data is incomplete."))
        cleaned_data["query"] = query
        return cleaned_data

    def _get_query_parts(self):
        query_dict = self.cleaned_data["query"]
        alias = query_dict.get("alias", "default")
        connection = connections[alias]
        collection_name, operation, args_list = parse_query_args(query_dict)
        db = connection.database
        return QueryParts(
            query_dict=query_dict,
            alias=alias,
            mql_string=query_dict.get("mql", ""),
            connection=connection,
            db=db,
            collection=db[collection_name],
            collection_name=collection_name,
            operation=operation,
            args_list=args_list,
        )

    def _handle_operation_error(self, error, mql_string, operation_type="operation"):
        error_map = {
            pymongo_errors.OperationFailure: (
                "MongoDB Operation Error",
                [
                    f"MongoDB operation failed: {error}",
                    "The query syntax may be invalid or the operation is not supported.",
                ],
            ),
            (
                pymongo_errors.ConnectionFailure,
                pymongo_errors.ServerSelectionTimeoutError,
            ): (
                "MongoDB Connection Error",
                [
                    f"MongoDB connection error: {error}",
                    "Could not connect to MongoDB server.",
                    "Check your database connection settings.",
                ],
            ),
            pymongo_errors.PyMongoError: (
                "MongoDB Error",
                [
                    f"MongoDB error: {error}",
                    "An error occurred while executing the MongoDB operation.",
                ],
            ),
        }
        header, messages = None, []
        for err_type, (_header, _messages) in error_map.items():
            if isinstance(error, err_type):
                header, messages = _header, _messages.copy()
                break
        if not header:
            if isinstance(error, ValueError):
                header = "Query Parsing Error"
                messages = [f"Query parsing error: {error}"]
                if operation_type == "select":
                    messages += [
                        "The MQL panel can only re-execute read operations.",
                        "Write operations (insert, update, delete) cannot be re-executed.",
                    ]
                else:
                    messages += [
                        "The MQL panel tracks raw MongoDB operations.",
                        "Some operations may not be re-executable from the debug toolbar.",
                    ]
            else:
                header = f"{operation_type.capitalize()} Error"
                messages = [
                    f"Unexpected error executing {operation_type}: {error}",
                    "An unexpected error occurred.",
                ]
        body_text = "\n\n".join(messages)
        formatted_body = body_text.split("\n")
        formatted_body.extend(["", f"Original query: {mql_string}"])
        # Return error in the same format as convert_documents_to_table():
        # a one-row table with {value, is_json} cells
        error_message = "\n".join(formatted_body)
        rows = [[{"value": error_message, "is_json": False}]]
        headers = [header]
        return rows, headers

    def _execute_operation(self, operation_type, executor_func):
        mql_string = ""
        try:
            parts = self._get_query_parts()
            mql_string = parts.mql_string
            return executor_func(
                parts.db,
                parts.collection,
                parts.collection_name,
                parts.operation,
                parts.args_list,
            )
        except (ValueError, pymongo_errors.PyMongoError) as e:
            # ValueError: unsupported operation or unserializable args.
            # PyMongoError: any MongoDB driver error during execution.
            return self._handle_operation_error(e, mql_string, operation_type)


class MQLExplainForm(MQLBaseForm):
    def _execute_aggregate(self, db, collection_name, args_list):
        pipeline = args_list[0] if args_list else []
        return db.command(
            "explain",
            {"aggregate": collection_name, "pipeline": pipeline, "cursor": {}},
        )

    def _execute_explain(self, db, collection, collection_name, operation, args_list):
        if operation == "aggregate":
            explain_result = self._execute_aggregate(db, collection_name, args_list)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
        explain_json = json_util.dumps(explain_result, indent=4)
        result = [[explain_json]]
        headers = ["MongoDB Explain Output (JSON)"]
        return result, headers

    def explain(self):
        return self._execute_operation("explain", self._execute_explain)


class MQLAggregateForm(MQLBaseForm):
    def _execute_aggregate(self, collection, args_list):
        pipeline = args_list[0] if args_list else []
        result_docs = []
        max_results = get_max_select_results()
        with collection.aggregate(pipeline) as cursor:
            for i, doc in enumerate(cursor):
                if i >= max_results:
                    break
                result_docs.append(doc)
        return result_docs

    def _execute_select(self, db, collection, collection_name, operation, args_list):
        if operation == "aggregate":
            result_docs = self._execute_aggregate(collection, args_list)
        else:
            raise ValueError(f"Unsupported read operation: {operation}")
        return self.convert_documents_to_table(result_docs)

    def select(self):
        return self._execute_operation("select", self._execute_select)

    def _format_cell_value(self, value):
        """Format a single cell value for table display."""
        if value is None:
            return {"value": "", "is_json": False}
        # Handle primitive types directly without JSON serialization
        if isinstance(value, (str, int, float, bool)):
            return {"value": str(value), "is_json": False}
        # For complex types (ObjectId, datetime, dicts, lists, etc.), use json_util
        try:
            serialized = json_util.dumps(value)
        except (TypeError, AttributeError):
            return {"value": str(value), "is_json": False}
        try:
            parsed = json.loads(serialized)
        except json.JSONDecodeError:
            return {"value": serialized, "is_json": False}
        # Extract value from single-key BSON extended JSON objects like {"$oid": "..."}
        if isinstance(parsed, dict) and len(parsed) == 1:
            key, val = next(iter(parsed.items()))
            return {"value": str(val), "is_json": False}
        # For multi-key objects, format with indentation for readability
        if isinstance(parsed, dict) and len(parsed) > 1:
            return {"value": json.dumps(parsed, indent=4), "is_json": True}
        # For lists and other types, use compact serialization
        return {"value": serialized, "is_json": False}

    def convert_documents_to_table(self, documents):
        """Convert MongoDB documents to a table of rows and headers."""
        if not documents:
            return [], []
        # Collect all unique field names
        all_fields = set()
        for doc in documents:
            all_fields.update(doc.keys())
        # Sort fields for consistent column ordering, with _id first if present
        headers = sorted(all_fields)
        if "_id" in headers:
            headers.remove("_id")
            headers.insert(0, "_id")
        # Convert each document to a row with formatted values
        rows = []
        for doc in documents:
            row = [self._format_cell_value(doc.get(field)) for field in headers]
            rows.append(row)
        return rows, headers

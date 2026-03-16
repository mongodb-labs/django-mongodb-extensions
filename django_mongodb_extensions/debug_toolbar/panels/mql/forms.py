from bson import json_util
from django import forms
from django.core.exceptions import ValidationError
from django.db import connections
from django.utils.translation import gettext_lazy as _
from pymongo import errors as pymongo_errors

from debug_toolbar.panels.sql.forms import SQLSelectForm
from debug_toolbar.toolbar import DebugToolbar
from django_mongodb_extensions.debug_toolbar.panels.mql.utils import (
    MQL_PANEL_ID,
    QueryParts,
    get_max_select_results,
    parse_query_args,
)
import json


class MQLBaseForm(SQLSelectForm):
    """Base form with shared validation and helpers."""

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
                q
                for q in stats["queries"]
                if isinstance(q, dict) and q.get("djdt_query_id") == djdt_query_id
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
            query_dict=self.cleaned_data["query"],
            alias=alias,
            mql_string=query_dict.get("mql", ""),
            connection=connections[alias],
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
        return [formatted_body], [header]

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

        except Exception as e:
            return self._handle_operation_error(e, mql_string, operation_type)


class MQLExplainForm(MQLBaseForm):
    def _execute_aggregate(self, db, collection_name, args_list):
        pipeline = args_list[0] if args_list else []
        return db.command(
            "explain",
            {"aggregate": collection_name, "pipeline": pipeline, "cursor": {}},
        )

    def _execute_find(self, collection, args_list):
        if len(args_list) >= 2:
            filter_doc, projection = args_list[0], args_list[1]
            cursor = collection.find(filter_doc, projection)
        elif len(args_list) == 1:
            filter_doc = args_list[0]
            cursor = collection.find(filter_doc)
        else:
            cursor = collection.find({})
        try:
            return cursor.explain()
        finally:
            cursor.close()

    def _execute_explain(self, db, collection, collection_name, operation, args_list):
        if operation == "aggregate":
            explain_result = self._execute_aggregate(db, collection_name, args_list)
        elif operation == "find":
            explain_result = self._execute_find(collection, args_list)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        explain_json = json_util.dumps(explain_result, indent=4)

        result = [[explain_json]]
        headers = ["MongoDB Explain Output (JSON)"]
        return result, headers

    def explain(self):
        return self._execute_operation("explain", self._execute_explain)


class MQLSelectForm(MQLBaseForm):
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

    def _execute_find(self, collection, args_list):
        max_results = get_max_select_results()
        if len(args_list) >= 2:
            filter_doc, projection = args_list[0], args_list[1]
            cursor = collection.find(filter_doc, projection)
        elif len(args_list) == 1:
            filter_doc = args_list[0]
            cursor = collection.find(filter_doc)
        else:
            cursor = collection.find({})
        try:
            return list(cursor.limit(max_results))
        finally:
            cursor.close()

    def _execute_select(self, db, collection, collection_name, operation, args_list):
        if operation == "aggregate":
            result_docs = self._execute_aggregate(collection, args_list)
        elif operation == "find":
            result_docs = self._execute_find(collection, args_list)
        else:
            raise ValueError(f"Unsupported read operation: {operation}")

        # Convert documents to table format with columns
        return self.convert_documents_to_table(result_docs)

    def select(self):
        return self._execute_operation("select", self._execute_select)

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
                    # For simple string values, return them directly without JSON quotes
                    if isinstance(value, str):
                        row.append({"value": value, "is_json": False})
                    else:
                        # For complex types, serialize with json_util
                        serialized = json_util.dumps(value)
                        # If the result is a single-key object like {"$oid": "..."} or {"$date": "..."},
                        # extract just the value. For multi-key objects, format with indentation.
                        try:
                            parsed = json.loads(serialized)
                            if isinstance(parsed, dict) and len(parsed) == 1:
                                # Extract the single value from objects like {"$oid": "..."}, {"$date": "..."}
                                row.append(
                                    {
                                        "value": str(list(parsed.values())[0]),
                                        "is_json": False,
                                    }
                                )
                            elif isinstance(parsed, dict) and len(parsed) > 1:
                                # For multi-key objects, format with indentation for readability
                                row.append(
                                    {
                                        "value": json_util.dumps(value, indent=4),
                                        "is_json": True,
                                    }
                                )
                            else:
                                row.append({"value": serialized, "is_json": False})
                        except (json.JSONDecodeError, TypeError, AttributeError):
                            row.append({"value": serialized, "is_json": False})
                else:
                    row.append({"value": "", "is_json": False})
            rows.append(row)

        return rows, headers

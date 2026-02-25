"""Forms for MQL panel."""

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
    convert_documents_to_table,
    get_max_select_results,
    parse_query_args,
)


class MQLBaseForm(SQLSelectForm):
    """Base form with shared validation and helpers."""

    def clean(self):
        cleaned_data = super(forms.Form, self).clean()

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
        mql_string = query_dict.get("mql", "")
        connection = connections[alias]
        collection_name, operation, args_list = parse_query_args(query_dict)
        db = connection.database
        collection = db[collection_name]

        return QueryParts(
            query_dict=query_dict,
            alias=alias,
            mql_string=mql_string,
            connection=connection,
            db=db,
            collection=collection,
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

        for err_type, (h, m) in error_map.items():
            if isinstance(error, err_type):
                header, messages = h, m.copy()
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

    def _execute_count(self, collection, args_list):
        filter_doc = args_list[0] if args_list else {}
        cursor = collection.find(filter_doc)
        try:
            return cursor.explain()
        finally:
            cursor.close()

    def explain(self):
        def _execute_explain(db, collection, collection_name, operation, args_list):
            """Inner function to execute the explain operation."""
            if operation == "aggregate":
                explain_result = self._execute_aggregate(db, collection_name, args_list)
            elif operation == "find":
                explain_result = self._execute_find(collection, args_list)
            elif operation == "count_documents":
                explain_result = self._execute_count(collection, args_list)
            else:
                raise ValueError(f"Unsupported operation: {operation}")

            explain_json = json_util.dumps(explain_result, indent=2)

            result = [[explain_json]]
            headers = ["MongoDB Explain Output (JSON)"]
            return result, headers

        return self._execute_operation("explain", _execute_explain)


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

    def _execute_count(self, collection, args_list):
        filter_doc = args_list[0] if args_list else {}
        count = collection.count_documents(filter_doc)
        return [{"count": count}]

    def select(self):
        def _execute_select(db, collection, collection_name, operation, args_list):
            """Inner function to execute the select operation."""
            if operation == "aggregate":
                result_docs = self._execute_aggregate(collection, args_list)
            elif operation == "find":
                result_docs = self._execute_find(collection, args_list)
            elif operation == "count_documents":
                result_docs = self._execute_count(collection, args_list)
            else:
                raise ValueError(f"Unsupported read operation: {operation}")

            # Convert documents to table format with columns
            return convert_documents_to_table(result_docs)

        return self._execute_operation("select", _execute_select)

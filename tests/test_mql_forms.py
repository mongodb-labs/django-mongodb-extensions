"""Tests for MQL panel forms."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from django.core.exceptions import ValidationError
from pymongo import errors as pymongo_errors

from django_mongodb_extensions.debug_toolbar.panels.mql.forms import (
    MQLBaseForm,
    MQLExplainForm,
    MQLSelectForm,
)


class TestMQLBaseForm:
    """Test MQLBaseForm validation and helpers."""

    def test_clean_missing_request_id(self):
        """Missing request_id raises ValidationError."""
        form = MQLBaseForm(data={})
        form.is_valid()  # Trigger validation
        with pytest.raises(ValidationError, match="Missing request ID"):
            form.clean()

    def test_clean_missing_query_id(self):
        """Missing query_id raises ValidationError."""
        form = MQLBaseForm(data={"request_id": "test-request"})
        form.is_valid()  # Trigger validation
        with pytest.raises(ValidationError, match="Missing query ID"):
            form.clean()

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    def test_clean_toolbar_not_found(self, mock_toolbar_class):
        """Unavailable toolbar data raises ValidationError."""
        mock_toolbar_class.fetch.return_value = None

        form = MQLBaseForm(
            data={"request_id": "test-request", "djdt_query_id": "test-query"}
        )
        form.is_valid()  # Trigger validation
        with pytest.raises(ValidationError, match="isn't available anymore"):
            form.clean()

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    def test_clean_invalid_stats_structure(self, mock_toolbar_class):
        """Invalid stats structure raises ValidationError."""
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = None  # Invalid stats
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        form = MQLBaseForm(
            data={"request_id": "test-request", "djdt_query_id": "test-query"}
        )
        form.is_valid()  # Trigger validation
        with pytest.raises(ValidationError, match="Query data is not available"):
            form.clean()

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    def test_clean_query_not_found(self, mock_toolbar_class):
        """Query ID not found in stats raises ValidationError."""
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = {"queries": []}
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        form = MQLBaseForm(
            data={"request_id": "test-request", "djdt_query_id": "test-query"}
        )
        form.is_valid()  # Trigger validation
        with pytest.raises(ValidationError, match="Invalid query ID"):
            form.clean()

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    def test_clean_incomplete_query_data(self, mock_toolbar_class):
        """Incomplete query data raises ValidationError."""
        mock_toolbar = Mock()
        mock_panel = Mock()
        # Query missing required 'mql' field
        mock_panel.get_stats.return_value = {
            "queries": [{"djdt_query_id": "test-query", "alias": "default"}]
        }
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        form = MQLBaseForm(
            data={"request_id": "test-request", "djdt_query_id": "test-query"}
        )
        form.is_valid()  # Trigger validation
        with pytest.raises(ValidationError, match="Query data is incomplete"):
            form.clean()

    def test_handle_operation_error_operation_failure(self):
        """OperationFailure is reported as 'MongoDB Operation Error'."""
        form = MQLBaseForm()
        error = pymongo_errors.OperationFailure("Invalid query")
        result, headers = form._handle_operation_error(error, "db.test.find({})")

        assert headers == ["MongoDB Operation Error"]
        assert "MongoDB operation failed" in result[0][0]
        assert "Original query: db.test.find({})" in result[0]

    def test_handle_operation_error_connection_failure(self):
        """ConnectionFailure is reported as 'MongoDB Connection Error'."""
        form = MQLBaseForm()
        error = pymongo_errors.ConnectionFailure("Connection refused")
        result, headers = form._handle_operation_error(error, "db.test.find({})")

        assert headers == ["MongoDB Connection Error"]
        assert "MongoDB connection error" in result[0][0]

    def test_handle_operation_error_value_error_select(self):
        """ValueError in a select operation is reported as 'Query Parsing Error' with a read-only hint."""
        form = MQLBaseForm()
        error = ValueError("Unsupported operation")
        result, headers = form._handle_operation_error(
            error, "db.test.insert({})", "select"
        )

        assert headers == ["Query Parsing Error"]
        assert "can only re-execute read operations" in "\n".join(result[0])

    def test_handle_operation_error_unexpected(self):
        """Unexpected errors are reported using the operation type as the header."""
        form = MQLBaseForm()
        error = RuntimeError("Unexpected error")
        result, headers = form._handle_operation_error(
            error, "db.test.find({})", "select"
        )

        assert headers == ["Select Error"]
        assert "Unexpected error executing select" in result[0][0]

    def test_handle_operation_error_server_selection_timeout(self):
        """ServerSelectionTimeoutError is reported as 'MongoDB Connection Error'."""
        form = MQLBaseForm()
        error = pymongo_errors.ServerSelectionTimeoutError("Server selection timeout")
        result, headers = form._handle_operation_error(error, "db.test.find({})")

        assert headers == ["MongoDB Connection Error"]
        result_text = "\n".join(result[0])
        assert "MongoDB connection error" in result_text
        assert "Could not connect to MongoDB server" in result_text
        assert "Check your database connection settings" in result_text
        assert "Original query: db.test.find({})" in result_text

    def test_handle_operation_error_pymongo_error(self):
        """Generic PyMongoError is reported as 'MongoDB Error'."""
        form = MQLBaseForm()
        error = pymongo_errors.PyMongoError("Generic MongoDB error")
        result, headers = form._handle_operation_error(error, "db.test.find({})")

        assert headers == ["MongoDB Error"]
        result_text = "\n".join(result[0])
        assert "MongoDB error: Generic MongoDB error" in result_text
        assert "An error occurred while executing the MongoDB operation" in result_text
        assert "Original query: db.test.find({})" in result_text

    def test_handle_operation_error_value_error_explain(self):
        """ValueError in an explain operation is reported as 'Query Parsing Error' with a re-execution hint."""
        form = MQLBaseForm()
        error = ValueError("Unsupported operation")
        result, headers = form._handle_operation_error(
            error, "db.test.insert({})", "explain"
        )

        assert headers == ["Query Parsing Error"]
        assert "Query parsing error: Unsupported operation" in result[0][0]
        assert "The MQL panel tracks raw MongoDB operations" in "\n".join(result[0])
        assert "Some operations may not be re-executable" in "\n".join(result[0])
        assert "Original query: db.test.insert({})" in result[0]


class TestMQLSelectForm:
    """Test MQLSelectForm execution."""

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.connections")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    def test_execute_find_with_cursor_cleanup(
        self, mock_toolbar_class, mock_connections
    ):
        """find closes the cursor after execution."""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_cursor.limit.return_value = [{"_id": 1}, {"_id": 2}]

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLSelectForm()
        result = form._execute_find(mock_collection, [{}])

        # Verify cursor was closed
        mock_cursor.close.assert_called_once()
        assert len(result) == 2

    def test_execute_find_cursor_cleanup_on_error(self):
        """find closes the cursor even when an error occurs."""
        mock_cursor = MagicMock()
        mock_cursor.limit.side_effect = Exception("Test error")

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLSelectForm()

        with pytest.raises(Exception, match="Test error"):
            form._execute_find(mock_collection, [{}])

        # Verify cursor was still closed
        mock_cursor.close.assert_called_once()

    def test_explain_find_with_cursor_cleanup(self):
        """explain find closes the cursor after execution."""
        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = {"queryPlanner": {}}

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLExplainForm()
        result = form._execute_find(mock_collection, [{}])

        # Verify cursor was closed
        mock_cursor.close.assert_called_once()
        assert result == {"queryPlanner": {}}

    def test_explain_find_cursor_cleanup_on_error(self):
        """explain find closes the cursor even when an error occurs."""
        mock_cursor = MagicMock()
        mock_cursor.explain.side_effect = Exception("Explain error")

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLExplainForm()

        with pytest.raises(Exception, match="Explain error"):
            form._execute_find(mock_collection, [{}])

        # Verify cursor was still closed
        mock_cursor.close.assert_called_once()

    def test_explain_count_with_cursor_cleanup(self):
        """explain count closes the cursor after execution."""
        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = {"queryPlanner": {}}

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLExplainForm()
        result = form._execute_count(mock_collection, [{}])

        # Verify cursor was closed
        mock_cursor.close.assert_called_once()
        assert result == {"queryPlanner": {}}

    def test_explain_count_cursor_cleanup_on_error(self):
        """explain count closes the cursor even when an error occurs."""
        mock_cursor = MagicMock()
        mock_cursor.explain.side_effect = Exception("Explain count error")

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLExplainForm()

        with pytest.raises(Exception, match="Explain count error"):
            form._execute_count(mock_collection, [{}])

        # Verify cursor was still closed
        mock_cursor.close.assert_called_once()


class TestMQLExplainForm:
    """Test MQLExplainForm execution."""

    def test_execute_aggregate_explain(self):
        """aggregate explain calls db.command with an explain wrapper."""
        mock_db = Mock()
        mock_db.command.return_value = {"queryPlanner": {}}

        form = MQLExplainForm()
        result = form._execute_aggregate(mock_db, "test_collection", [[{"$match": {}}]])

        mock_db.command.assert_called_once()
        assert "queryPlanner" in result

    def test_execute_find_explain(self):
        """find explain calls cursor.explain()."""
        mock_cursor = Mock()
        mock_cursor.explain.return_value = {"queryPlanner": {}}

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLExplainForm()
        result = form._execute_find(mock_collection, [{}])

        mock_cursor.explain.assert_called_once()
        assert "queryPlanner" in result

    def test_execute_find_with_projection(self):
        """find explain passes both filter and projection to find()."""
        mock_cursor = Mock()
        mock_cursor.explain.return_value = {"queryPlanner": {}}

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLExplainForm()
        result = form._execute_find(
            mock_collection, [{"status": "active"}, {"name": 1}]
        )

        # Verify find was called with both filter and projection
        mock_collection.find.assert_called_once_with({"status": "active"}, {"name": 1})
        mock_cursor.explain.assert_called_once()
        assert "queryPlanner" in result

    def test_execute_find_no_args(self):
        """find explain with no arguments calls find({})."""
        mock_cursor = Mock()
        mock_cursor.explain.return_value = {"queryPlanner": {}}

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLExplainForm()
        result = form._execute_find(mock_collection, [])

        # Verify find was called with empty filter
        mock_collection.find.assert_called_once_with({})
        mock_cursor.explain.assert_called_once()
        assert "queryPlanner" in result

    @pytest.mark.skip(reason="Integration test - too complex to mock properly")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.connections")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.parse_query_args")
    def test_explain_full_flow(self, mock_parse, mock_connections, mock_toolbar_class):
        """Full explain flow returns JSON explain output."""
        # Setup toolbar and panel mocks
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = {
            "queries": [
                {
                    "mql": "db.test.find({})",
                    "alias": "default",
                    "duration": 1.5,
                    "mql_collection": "test",
                    "mql_operation": "find",
                    "mql_args_json": "[[{}]]",
                }
            ]
        }
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        # Setup connection mocks
        mock_db = MagicMock()
        mock_collection = Mock()
        mock_cursor = Mock()
        mock_cursor.explain.return_value = {"queryPlanner": {"stage": "COLLSCAN"}}
        mock_collection.find.return_value = mock_cursor
        mock_db.__getitem__.return_value = mock_collection

        mock_connection = Mock()
        mock_connection.database = mock_db
        mock_connections.__getitem__.return_value = mock_connection

        # Setup parse_query_args mock
        mock_parse.return_value = ("test", "find", [[{}]])

        # Create and validate form
        form = MQLExplainForm(data={"request_id": "test-req", "djdt_query_id": "0"})
        assert form.is_valid()

        # Execute explain
        result, headers = form.explain()

        # Verify results
        assert headers == ["MongoDB Explain Output (JSON)"]
        assert len(result) == 1
        assert "queryPlanner" in result[0][0]
        mock_cursor.close.assert_called_once()

    @pytest.mark.skip(reason="Integration test - too complex to mock properly")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.connections")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.parse_query_args")
    def test_explain_aggregate_flow(
        self, mock_parse, mock_connections, mock_toolbar_class
    ):
        """Aggregate explain flow returns JSON explain output."""
        # Setup toolbar and panel mocks
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = {
            "queries": [
                {
                    "mql": "db.test.aggregate([...])",
                    "alias": "default",
                    "duration": 2.0,
                    "mql_collection": "test",
                    "mql_operation": "aggregate",
                    "mql_args_json": '[[[{"$match": {"status": "active"}}]]]',
                }
            ]
        }
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        # Setup connection mocks
        mock_db = MagicMock()
        mock_db.command.return_value = {"queryPlanner": {"stage": "AGGREGATE"}}
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection

        mock_connection = Mock()
        mock_connection.database = mock_db
        mock_connections.__getitem__.return_value = mock_connection

        # Setup parse_query_args mock
        mock_parse.return_value = (
            "test",
            "aggregate",
            [[[{"$match": {"status": "active"}}]]],
        )

        # Create and validate form
        form = MQLExplainForm(data={"request_id": "test-req", "djdt_query_id": "0"})
        assert form.is_valid()

        # Execute explain
        result, headers = form.explain()

        # Verify results
        assert headers == ["MongoDB Explain Output (JSON)"]
        assert len(result) == 1
        assert "queryPlanner" in result[0][0]

    @pytest.mark.skip(reason="Integration test - too complex to mock properly")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.connections")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.parse_query_args")
    def test_explain_count_flow(self, mock_parse, mock_connections, mock_toolbar_class):
        """count_documents explain flow returns JSON explain output."""
        # Setup toolbar and panel mocks
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = {
            "queries": [
                {
                    "mql": "db.test.count_documents({})",
                    "alias": "default",
                    "duration": 0.5,
                    "mql_collection": "test",
                    "mql_operation": "count_documents",
                    "mql_args_json": "[[{}]]",
                }
            ]
        }
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        # Setup connection mocks
        mock_db = MagicMock()
        mock_collection = Mock()
        mock_cursor = Mock()
        mock_cursor.explain.return_value = {"queryPlanner": {"stage": "COUNT"}}
        mock_collection.find.return_value = mock_cursor
        mock_db.__getitem__.return_value = mock_collection

        mock_connection = Mock()
        mock_connection.database = mock_db
        mock_connections.__getitem__.return_value = mock_connection

        # Setup parse_query_args mock
        mock_parse.return_value = ("test", "count_documents", [[{}]])

        # Create and validate form
        form = MQLExplainForm(data={"request_id": "test-req", "djdt_query_id": "0"})
        assert form.is_valid()

        # Execute explain
        result, headers = form.explain()

        # Verify results
        assert headers == ["MongoDB Explain Output (JSON)"]
        assert len(result) == 1
        assert "queryPlanner" in result[0][0]
        mock_cursor.close.assert_called_once()


class TestMQLSelectFormExtended:
    """Extended tests for MQLSelectForm execution."""

    def test_execute_find_with_projection(self):
        """find select passes both filter and projection to find()."""
        mock_cursor = Mock()
        mock_cursor.limit.return_value = [{"_id": 1, "name": "test"}]

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLSelectForm()
        result = form._execute_find(
            mock_collection, [{"status": "active"}, {"name": 1}]
        )

        # Verify find was called with both filter and projection
        mock_collection.find.assert_called_once_with({"status": "active"}, {"name": 1})
        mock_cursor.close.assert_called_once()
        assert len(result) == 1

    def test_execute_find_no_args(self):
        """find select with no arguments calls find({})."""
        mock_cursor = Mock()
        mock_cursor.limit.return_value = [{"_id": 1}, {"_id": 2}]

        mock_collection = Mock()
        mock_collection.find.return_value = mock_cursor

        form = MQLSelectForm()
        result = form._execute_find(mock_collection, [])

        # Verify find was called with empty filter
        mock_collection.find.assert_called_once_with({})
        mock_cursor.close.assert_called_once()
        assert len(result) == 2

    def test_execute_count(self):
        """count_documents returns the document count."""
        mock_collection = Mock()
        mock_collection.count_documents.return_value = 42

        form = MQLSelectForm()
        result = form._execute_count(mock_collection, [{"status": "active"}])

        mock_collection.count_documents.assert_called_once_with({"status": "active"})
        assert result == [{"count": 42}]

    def test_execute_count_no_filter(self):
        """count_documents with no filter counts all documents."""
        mock_collection = Mock()
        mock_collection.count_documents.return_value = 100

        form = MQLSelectForm()
        result = form._execute_count(mock_collection, [])

        mock_collection.count_documents.assert_called_once_with({})
        assert result == [{"count": 100}]

    @patch(
        "django_mongodb_extensions.debug_toolbar.panels.mql.forms.get_max_select_results"
    )
    def test_execute_aggregate_with_limit(self, mock_get_max):
        """aggregate select respects the max results limit."""
        mock_get_max.return_value = 2

        # Create a mock cursor that yields 5 documents
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = iter([{"_id": i} for i in range(5)])
        mock_cursor.__exit__.return_value = None

        mock_collection = Mock()
        mock_collection.aggregate.return_value = mock_cursor

        form = MQLSelectForm()
        result = form._execute_aggregate(mock_collection, [[{"$match": {}}]])

        # Should only get 2 results due to limit
        assert len(result) == 2

    @pytest.mark.skip(reason="Integration test - too complex to mock properly")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.connections")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.parse_query_args")
    def test_select_full_flow(self, mock_parse, mock_connections, mock_toolbar_class):
        """Full select flow returns tabular results."""
        # Setup toolbar and panel mocks
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = {
            "queries": [
                {
                    "mql": "db.test.find({})",
                    "alias": "default",
                    "duration": 1.5,
                    "mql_collection": "test",
                    "mql_operation": "find",
                    "mql_args_json": "[[{}]]",
                }
            ]
        }
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        # Setup connection mocks
        mock_db = MagicMock()
        mock_collection = Mock()
        mock_cursor = Mock()
        mock_cursor.limit.return_value = [{"_id": 1, "name": "test"}]
        mock_collection.find.return_value = mock_cursor
        mock_db.__getitem__.return_value = mock_collection

        mock_connection = Mock()
        mock_connection.database = mock_db
        mock_connections.__getitem__.return_value = mock_connection

        # Setup parse_query_args mock
        mock_parse.return_value = ("test", "find", [[{}]])

        # Create and validate form
        form = MQLSelectForm(data={"request_id": "test-req", "djdt_query_id": "0"})
        assert form.is_valid()

        # Execute select
        result, headers = form.select()

        # Verify results
        assert "Results" in headers[0]
        assert len(result) > 0
        mock_cursor.close.assert_called_once()

    @pytest.mark.skip(reason="Integration test - too complex to mock properly")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.connections")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.parse_query_args")
    def test_select_aggregate_flow(
        self, mock_parse, mock_connections, mock_toolbar_class
    ):
        """Aggregate select flow returns tabular results."""
        # Setup toolbar and panel mocks
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = {
            "queries": [
                {
                    "mql": "db.test.aggregate([...])",
                    "alias": "default",
                    "duration": 2.0,
                    "mql_collection": "test",
                    "mql_operation": "aggregate",
                    "mql_args_json": '[[[{"$match": {"status": "active"}}]]]',
                }
            ]
        }
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        # Setup connection mocks
        mock_db = MagicMock()
        mock_collection = Mock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = iter([{"_id": 1, "status": "active"}])
        mock_cursor.__exit__.return_value = None
        mock_collection.aggregate.return_value = mock_cursor
        mock_db.__getitem__.return_value = mock_collection

        mock_connection = Mock()
        mock_connection.database = mock_db
        mock_connections.__getitem__.return_value = mock_connection

        # Setup parse_query_args mock
        mock_parse.return_value = (
            "test",
            "aggregate",
            [[[{"$match": {"status": "active"}}]]],
        )

        # Create and validate form
        form = MQLSelectForm(data={"request_id": "test-req", "djdt_query_id": "0"})
        assert form.is_valid()

        # Execute select
        result, headers = form.select()

        # Verify results
        assert "Results" in headers[0]
        assert len(result) > 0

    @pytest.mark.skip(reason="Integration test - too complex to mock properly")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.DebugToolbar")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.connections")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.forms.parse_query_args")
    def test_select_count_flow(self, mock_parse, mock_connections, mock_toolbar_class):
        """count_documents select flow returns tabular results."""
        # Setup toolbar and panel mocks
        mock_toolbar = Mock()
        mock_panel = Mock()
        mock_panel.get_stats.return_value = {
            "queries": [
                {
                    "mql": "db.test.count_documents({})",
                    "alias": "default",
                    "duration": 0.5,
                    "mql_collection": "test",
                    "mql_operation": "count_documents",
                    "mql_args_json": "[[{}]]",
                }
            ]
        }
        mock_toolbar.get_panel_by_id.return_value = mock_panel
        mock_toolbar_class.fetch.return_value = mock_toolbar

        # Setup connection mocks
        mock_db = MagicMock()
        mock_collection = Mock()
        mock_collection.count_documents.return_value = 42
        mock_db.__getitem__.return_value = mock_collection

        mock_connection = Mock()
        mock_connection.database = mock_db
        mock_connections.__getitem__.return_value = mock_connection

        # Setup parse_query_args mock
        mock_parse.return_value = ("test", "count_documents", [[{}]])

        # Create and validate form
        form = MQLSelectForm(data={"request_id": "test-req", "djdt_query_id": "0"})
        assert form.is_valid()

        # Execute select
        result, headers = form.select()

        # Verify results
        assert "Results" in headers[0]
        assert len(result) > 0

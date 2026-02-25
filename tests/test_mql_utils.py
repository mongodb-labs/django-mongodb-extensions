"""Tests for MQL panel utilities."""

import weakref
from unittest.mock import Mock, patch

import pytest
from bson import ObjectId, json_util

from django_mongodb_extensions.debug_toolbar.panels.mql.utils import (
    DebugToolbarWrapper,
    convert_documents_to_table,
    format_mql_query,
    get_max_select_results,
    hex_to_rgb,
    is_read_operation,
    parse_query_args,
    patch_get_collection,
    patch_new_connection,
    process_query_groups,
    query_key_duplicate,
    query_key_similar,
)


class TestGetMaxSelectResults:
    """Test get_max_select_results function."""

    def test_default_value(self):
        """Test default value when setting not configured."""
        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.utils.settings"
        ) as mock_settings:
            del mock_settings.DJDT_MQL_MAX_SELECT_RESULTS
            assert get_max_select_results() == 100

    def test_custom_value(self):
        """Test custom value from settings."""
        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.utils.settings"
        ) as mock_settings:
            mock_settings.DJDT_MQL_MAX_SELECT_RESULTS = 50
            assert get_max_select_results() == 50


class TestPatchGetCollection:
    """Test patch_get_collection function."""

    def test_idempotent_patching(self):
        """Test that patching the same connection multiple times is safe."""
        connection = Mock()
        connection.get_collection = Mock(return_value="original")

        # Patch once
        patch_get_collection(connection)
        assert hasattr(connection, "_original_get_collection")

        # Patch again - should not raise error
        patch_get_collection(connection)
        assert hasattr(connection, "_original_get_collection")

    def test_weakset_cleanup(self):
        """Test that WeakSet allows garbage collection of connections."""
        import gc
        from django_mongodb_extensions.debug_toolbar.panels.mql.utils import (
            _patched_connections,
        )

        # Create a connection and patch it
        connection = Mock()
        connection.get_collection = Mock()
        patch_get_collection(connection)

        # Verify it's in the WeakSet
        assert connection in _patched_connections

        # Create a weak reference to track when it's garbage collected
        weak_ref = weakref.ref(connection)

        # Delete the connection
        del connection

        # Force garbage collection
        gc.collect()

        # The weak reference should now return None (object was garbage collected)
        assert weak_ref() is None


class TestParseArgs:
    """Test parse_query_args function."""

    def test_parse_valid_structured_data(self):
        """Test parsing query with valid structured data."""
        query_dict = {
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": json_util.dumps([{"_id": ObjectId()}]),
        }

        collection, operation, args = parse_query_args(query_dict)
        assert collection == "users"
        assert operation == "find"
        assert isinstance(args, list)
        assert len(args) == 1

    def test_parse_empty_args(self):
        """Test parsing query with no arguments."""
        query_dict = {
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": "",
        }

        collection, operation, args = parse_query_args(query_dict)
        assert collection == "users"
        assert operation == "find"
        assert args == []

    def test_missing_structured_data(self):
        """Test that queries without structured data raise ValueError."""
        query_dict = {"sql": "db.users.find({})"}

        with pytest.raises(ValueError, match="does not have structured data"):
            parse_query_args(query_dict)

    def test_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        query_dict = {
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": "invalid json{",
        }

        with pytest.raises(ValueError, match="Failed to parse query arguments JSON"):
            parse_query_args(query_dict)


class TestQueryKeys:
    """Test query key generation functions."""

    def test_query_key_similar_with_structured_data(self):
        """Test query_key_similar with structured data."""
        query = {
            "mql_collection": "users",
            "mql_operation": "find",
        }
        assert query_key_similar(query) == "db.users.find()"

    def test_query_key_duplicate(self):
        """Test query_key_duplicate returns full query."""
        query = {"mql": "db.users.find({'_id': ObjectId('123')})"}
        assert query_key_duplicate(query) == "db.users.find({'_id': ObjectId('123')})"


class TestHexToRgb:
    """Test hex_to_rgb function."""

    def test_valid_hex_with_hash(self):
        """Test conversion of valid hex color with hash."""
        assert hex_to_rgb("#FF5733") == [255, 87, 51]

    def test_valid_hex_without_hash(self):
        """Test conversion of valid hex color without hash."""
        assert hex_to_rgb("FF5733") == [255, 87, 51]

    def test_invalid_length(self):
        """Test invalid hex color length returns default gray."""
        assert hex_to_rgb("#FFF") == [128, 128, 128]

    def test_invalid_characters(self):
        """Test invalid hex characters return default gray."""
        assert hex_to_rgb("GGGGGG") == [128, 128, 128]


class TestIsReadOperation:
    """Test is_read_operation function."""

    def test_read_operations(self):
        """Test that read operations are correctly identified."""
        assert is_read_operation("find") is True
        assert is_read_operation("aggregate") is True
        assert is_read_operation("count_documents") is True

    def test_write_operations(self):
        """Test that write operations are correctly identified."""
        assert is_read_operation("insert_one") is False
        assert is_read_operation("update_one") is False
        assert is_read_operation("delete_one") is False

    def test_unsupported_read_operations(self):
        """Test that unsupported read operations are not included."""
        # These are valid PyMongo read operations but not supported by the debug toolbar
        assert is_read_operation("find_one") is False
        assert is_read_operation("distinct") is False
        assert is_read_operation("estimated_document_count") is False
        assert is_read_operation("count") is False
        assert is_read_operation("find_raw_batches") is False
        assert is_read_operation("find_one_and_delete") is False
        assert is_read_operation("find_one_and_replace") is False
        assert is_read_operation("find_one_and_update") is False


class TestConvertDocumentsToTable:
    """Test convert_documents_to_table function."""

    def test_empty_documents(self):
        """Test with empty document list."""
        rows, headers = convert_documents_to_table([])
        assert rows == []
        assert headers == []

    def test_single_document(self):
        """Test with a single document."""
        docs = [
            {"_id": ObjectId("507f1f77bcf86cd799439011"), "name": "Alice", "age": 30}
        ]
        rows, headers = convert_documents_to_table(docs)

        # _id should be first
        assert headers == ["_id", "age", "name"]
        assert len(rows) == 1
        # Check that values are JSON serialized
        assert '"Alice"' in rows[0][2]  # name field
        assert "30" in rows[0][1]  # age field

    def test_multiple_documents_same_fields(self):
        """Test with multiple documents having the same fields."""
        docs = [
            {"_id": 1, "name": "Alice", "age": 30},
            {"_id": 2, "name": "Bob", "age": 25},
        ]
        rows, headers = convert_documents_to_table(docs)

        assert headers == ["_id", "age", "name"]
        assert len(rows) == 2
        assert "1" in rows[0][0]
        assert "2" in rows[1][0]

    def test_multiple_documents_different_fields(self):
        """Test with documents having different fields."""
        docs = [
            {"_id": 1, "name": "Alice", "age": 30},
            {"_id": 2, "name": "Bob", "city": "NYC"},
            {"_id": 3, "age": 35, "city": "LA"},
        ]
        rows, headers = convert_documents_to_table(docs)

        # Should have all unique fields
        assert "_id" in headers
        assert "name" in headers
        assert "age" in headers
        assert "city" in headers
        assert headers[0] == "_id"  # _id should be first

        # Check that missing fields are empty strings
        assert len(rows) == 3
        # Second doc has no age
        age_idx = headers.index("age")
        assert rows[1][age_idx] == ""

    def test_null_values(self):
        """Test that null/None values are handled as empty strings."""
        docs = [
            {"_id": 1, "name": "Alice", "age": None},
            {"_id": 2, "name": None, "age": 30},
        ]
        rows, headers = convert_documents_to_table(docs)

        assert headers == ["_id", "age", "name"]
        # None values should be empty strings
        age_idx = headers.index("age")
        name_idx = headers.index("name")
        assert rows[0][age_idx] == ""
        assert rows[1][name_idx] == ""

    def test_complex_values(self):
        """Test with complex nested values."""
        docs = [
            {
                "_id": 1,
                "name": "Alice",
                "address": {"city": "NYC", "zip": "10001"},
                "tags": ["python", "mongodb"],
            }
        ]
        rows, headers = convert_documents_to_table(docs)

        assert headers == ["_id", "address", "name", "tags"]
        # Complex values should be JSON serialized
        address_idx = headers.index("address")
        tags_idx = headers.index("tags")
        assert "NYC" in rows[0][address_idx]
        assert "python" in rows[0][tags_idx]

    def test_no_id_field(self):
        """Test with documents that don't have _id field."""
        docs = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        rows, headers = convert_documents_to_table(docs)

        # Should work fine without _id
        assert headers == ["age", "name"]
        assert len(rows) == 2


class TestDebugToolbarWrapper:
    """Test DebugToolbarWrapper class."""

    def test_log_with_logger(self):
        """Test logging when logger is present."""
        mock_db = Mock()
        mock_db.alias = "default"
        mock_collection = Mock()
        mock_collection.name = "users"
        mock_logger = Mock()

        wrapper = DebugToolbarWrapper(mock_db, mock_collection, mock_logger)

        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.utils.get_stack_trace"
        ) as mock_trace:
            mock_trace.return_value = ["frame1", "frame2"]
            wrapper.log(".find", 10.5, [{"status": "active"}])

        # Verify logger.record was called
        mock_logger.record.assert_called_once()
        call_args = mock_logger.record.call_args[1]
        assert call_args["alias"] == "default"
        assert call_args["duration"] == 10.5
        assert call_args["mql_operation"] == "find"

    def test_log_without_logger(self):
        """Test logging when logger is None."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.name = "users"

        wrapper = DebugToolbarWrapper(mock_db, mock_collection, None)

        # Should not raise even without logger
        wrapper.log(".find", 10.5, [{"status": "active"}])

    def test_log_with_json_serialization_error(self):
        """Test logging when args can't be JSON serialized."""
        mock_db = Mock()
        mock_db.alias = "default"
        mock_collection = Mock()
        mock_collection.name = "users"
        mock_logger = Mock()

        wrapper = DebugToolbarWrapper(mock_db, mock_collection, mock_logger)

        # Create an object that can't be JSON serialized
        class UnserializableObject:
            pass

        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.utils.get_stack_trace"
        ) as mock_trace:
            mock_trace.return_value = []
            wrapper.log(".find", 10.5, [UnserializableObject()])

        # Verify logger.record was called with args_json=None
        mock_logger.record.assert_called_once()
        call_args = mock_logger.record.call_args[1]
        assert call_args["mql_args_json"] is None


class TestFormatMqlQuery:
    """Test format_mql_query function."""

    def test_format_valid_query(self):
        """Test formatting a valid query."""
        query = {
            "mql": "db.users.find({})",
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": json_util.dumps([{"status": "active"}]),
        }

        result = format_mql_query(query)
        assert "db.users.find(" in result
        assert "status" in result
        assert "active" in result

    def test_format_query_with_exception(self):
        """Test that exceptions return original mql string."""
        query = {
            "mql": "db.users.find({})",
            # Missing required fields to trigger exception
        }

        result = format_mql_query(query)
        assert result == "db.users.find({})"

    def test_format_query_empty_args(self):
        """Test formatting query with no arguments."""
        query = {
            "mql": "db.users.find()",
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": json_util.dumps([]),
        }

        result = format_mql_query(query)
        assert "db.users.find(" in result


class TestParseQueryArgsEdgeCases:
    """Test edge cases for parse_query_args."""

    def test_missing_collection_name(self):
        """Test that missing collection name raises ValueError."""
        query_dict = {
            "mql_collection": "",
            "mql_operation": "find",
            "mql_args_json": "[]",
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            parse_query_args(query_dict)

    def test_missing_operation(self):
        """Test that missing operation raises ValueError."""
        query_dict = {
            "mql_collection": "users",
            "mql_operation": "",
            "mql_args_json": "[]",
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            parse_query_args(query_dict)

    def test_none_args_json(self):
        """Test that None args_json returns empty list."""
        query_dict = {
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": None,
        }

        collection, operation, args = parse_query_args(query_dict)
        assert args == []


class TestPatchNewConnection:
    """Test patch_new_connection signal handler."""

    def test_patch_mongodb_connection(self):
        """Test that MongoDB connections are patched."""
        mock_connection = Mock()
        mock_connection.database = Mock()
        mock_connection.get_collection = Mock()

        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.utils.patch_get_collection"
        ) as mock_patch:
            patch_new_connection(sender=None, connection=mock_connection)
            mock_patch.assert_called_once_with(mock_connection)

    def test_ignore_non_mongodb_connection(self):
        """Test that non-MongoDB connections are ignored."""
        mock_connection = Mock(spec=[])  # Empty spec means no attributes
        # Missing database or get_collection attributes

        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.utils.patch_get_collection"
        ) as mock_patch:
            patch_new_connection(sender=None, connection=mock_connection)
            mock_patch.assert_not_called()


class TestPatchGetCollectionEdgeCases:
    """Test edge cases for patch_get_collection."""

    def test_get_collection_without_logger(self):
        """Test that get_collection works without logger."""
        from django_mongodb_extensions.debug_toolbar.panels.mql.utils import (
            _patched_connections,
        )

        mock_connection = Mock()
        original_collection = Mock()
        original_get_collection = Mock(return_value=original_collection)
        mock_connection.get_collection = original_get_collection

        # Clear patched connections to ensure clean state
        _patched_connections.clear()

        patch_get_collection(mock_connection)

        # Call get_collection without logger
        mock_connection._djdt_logger = None
        result = mock_connection.get_collection("test_collection")

        # Should call the original method (now stored in _original_get_collection)
        mock_connection._original_get_collection.assert_called_once_with(
            "test_collection"
        )
        # Result should be what the original method returned
        assert result is not None

    def test_get_collection_with_logger(self):
        """Test that get_collection wraps collection when logger is present."""
        mock_connection = Mock()
        original_collection = Mock()
        mock_connection.get_collection = Mock(return_value=original_collection)
        mock_logger = Mock()

        patch_get_collection(mock_connection)

        # Call get_collection with logger
        mock_connection._djdt_logger = mock_logger
        result = mock_connection.get_collection("test_collection")

        # Should return wrapped collection
        assert isinstance(result, DebugToolbarWrapper)


class TestProcessQueryGroups:
    """Test process_query_groups function."""

    def test_process_single_query_group(self):
        """Test that single queries are not marked as similar/duplicate."""
        query_groups = {
            ("default", "key1"): [{"mql": "db.users.find({})"}],
        }
        databases = {"default": {}}

        def color_generator():
            yield "#FF0000"
            yield "#00FF00"

        colors = color_generator()

        process_query_groups(query_groups, databases, colors, "similar")

        # Single query should not have similar_count
        assert "similar_count" not in query_groups[("default", "key1")][0]
        assert databases["default"]["similar_count"] == 0

    def test_process_multiple_query_group(self):
        """Test that multiple queries are marked with count and color."""
        query1 = {"mql": "db.users.find({})"}
        query2 = {"mql": "db.users.find({'status': 'active'})"}
        query_groups = {
            ("default", "key1"): [query1, query2],
        }
        databases = {"default": {}}

        def color_generator():
            yield "#FF0000"
            yield "#00FF00"

        colors = color_generator()

        process_query_groups(query_groups, databases, colors, "duplicate")

        # Both queries should have duplicate_count and duplicate_color
        assert query1["duplicate_count"] == 2
        assert query2["duplicate_count"] == 2
        assert query1["duplicate_color"] == "#FF0000"
        assert query2["duplicate_color"] == "#FF0000"
        assert databases["default"]["duplicate_count"] == 2

    def test_process_multiple_aliases(self):
        """Test processing queries from multiple database aliases."""
        query1 = {"mql": "db.users.find({})"}
        query2 = {"mql": "db.users.find({})"}
        query3 = {"mql": "db.posts.find({})"}
        query4 = {"mql": "db.posts.find({})"}

        query_groups = {
            ("default", "key1"): [query1, query2],
            ("secondary", "key2"): [query3, query4],
        }
        databases = {"default": {}, "secondary": {}}

        def color_generator():
            yield "#FF0000"
            yield "#00FF00"

        colors = color_generator()

        process_query_groups(query_groups, databases, colors, "similar")

        # Each alias should have its own count
        assert databases["default"]["similar_count"] == 2
        assert databases["secondary"]["similar_count"] == 2
        # Different groups should have different colors
        assert query1["similar_color"] == "#FF0000"
        assert query3["similar_color"] == "#00FF00"

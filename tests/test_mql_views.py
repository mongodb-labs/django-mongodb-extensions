"""Tests for MQL panel views."""

from unittest.mock import Mock, patch

from bson import json_util

from django_mongodb_extensions.debug_toolbar.panels.mql.utils import (
    format_mql_query,
)


class TestFormatMqlQuery:
    """Test format_mql_query function."""

    def test_format_simple_query(self):
        """Test formatting a simple query."""
        query = {
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": json_util.dumps([{}]),
        }

        assert format_mql_query(query) == "db.users.find(\n{}\n)"

    def test_format_query_with_multiple_args(self):
        """Test formatting a query with multiple arguments."""
        query = {
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": json_util.dumps([{}, {"name": 1}]),
        }

        assert format_mql_query(query) == "db.users.find(\n[{}, {'name': 1}]\n)"

    def test_format_query_fallback_on_error(self):
        """Test that formatting falls back to original MQL on error."""
        query = {
            "mql": "db.users.find({})",
            # Missing required fields to trigger error
        }

        assert format_mql_query(query) == "db.users.find({})"

    def test_format_aggregate_query(self):
        """Test formatting an aggregate query."""
        pipeline = [{"$match": {"status": "active"}}, {"$group": {"_id": "$category"}}]
        query = {
            "mql_collection": "users",
            "mql_operation": "aggregate",
            "mql_args_json": json_util.dumps([pipeline]),
        }

        assert (
            format_mql_query(query)
            == "db.users.aggregate(\n[{'$match': {'status': 'active'}}, {'$group': {'_id': '$category'}}]\n)"
        )

    def test_format_query_no_args(self):
        """Test formatting a query with no arguments."""
        query = {
            "mql_collection": "users",
            "mql_operation": "find",
            "mql_args_json": json_util.dumps([]),
        }

        assert format_mql_query(query) == "db.users.find(\n\n)"


class TestMqlExplainView:
    """Test mql_explain view."""

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.views.get_signed_data")
    def test_invalid_signature(self, mock_get_signed_data):
        """Test that invalid signature returns bad request."""
        # Import and patch the decorator before importing the view
        with patch("debug_toolbar.decorators.require_show_toolbar", lambda f: f):
            # Force reimport to get the patched decorator
            import importlib
            from django_mongodb_extensions.debug_toolbar.panels.mql import (
                views as mql_views,
            )

            importlib.reload(mql_views)

            mock_get_signed_data.return_value = None
            mock_request = Mock()

            response = mql_views.mql_explain(mock_request)
            assert response.status_code == 400
            assert b"Invalid signature" in response.content

    def test_valid_form_submission(self):
        """Test successful explain form submission."""
        with patch("debug_toolbar.decorators.require_show_toolbar", lambda f: f):
            import importlib
            from django_mongodb_extensions.debug_toolbar.panels.mql import (
                views as mql_views,
            )

            importlib.reload(mql_views)

            with patch.object(
                mql_views, "get_signed_data"
            ) as mock_get_signed_data, patch.object(
                mql_views, "MQLExplainForm"
            ) as mock_form_class, patch.object(
                mql_views, "render_to_string"
            ) as mock_render_to_string:
                # Setup mocks
                mock_get_signed_data.return_value = {"test": "data"}
                mock_form = Mock()
                mock_form.is_valid.return_value = True
                mock_form.cleaned_data = {
                    "query": {
                        "mql": "db.test.find({})",
                        "duration": 1.5,
                        "alias": "default",
                        "mql_collection": "test",
                        "mql_operation": "find",
                        "mql_args_json": json_util.dumps([{}]),
                    }
                }
                mock_form.explain.return_value = ([["result"]], ["header"])
                mock_form_class.return_value = mock_form
                mock_render_to_string.return_value = "<html>content</html>"

                mock_request = Mock()
                response = mql_views.mql_explain(mock_request)

                assert response.status_code == 200
                assert mock_form.explain.called
                assert mock_render_to_string.called

    def test_invalid_form(self):
        """Test that invalid form returns bad request."""
        with patch("debug_toolbar.decorators.require_show_toolbar", lambda f: f):
            import importlib
            from django_mongodb_extensions.debug_toolbar.panels.mql import (
                views as mql_views,
            )

            importlib.reload(mql_views)

            with patch.object(
                mql_views, "get_signed_data"
            ) as mock_get_signed_data, patch.object(
                mql_views, "MQLExplainForm"
            ) as mock_form_class:
                mock_get_signed_data.return_value = {"test": "data"}
                mock_form = Mock()
                mock_form.is_valid.return_value = False
                mock_form_class.return_value = mock_form

                mock_request = Mock()
                response = mql_views.mql_explain(mock_request)

                assert response.status_code == 400
                assert b"Form errors" in response.content


class TestMqlSelectView:
    """Test mql_select view."""

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.views.get_signed_data")
    def test_invalid_signature(self, mock_get_signed_data):
        """Test that invalid signature returns bad request."""
        # Import and patch the decorator before importing the view
        with patch("debug_toolbar.decorators.require_show_toolbar", lambda f: f):
            # Force reimport to get the patched decorator
            import importlib
            from django_mongodb_extensions.debug_toolbar.panels.mql import (
                views as mql_views,
            )

            importlib.reload(mql_views)

            mock_get_signed_data.return_value = None
            mock_request = Mock()

            response = mql_views.mql_select(mock_request)
            assert response.status_code == 400
            assert b"Invalid signature" in response.content

    def test_valid_form_submission(self):
        """Test successful select form submission."""
        with patch("debug_toolbar.decorators.require_show_toolbar", lambda f: f):
            import importlib
            from django_mongodb_extensions.debug_toolbar.panels.mql import (
                views as mql_views,
            )

            importlib.reload(mql_views)

            with patch.object(
                mql_views, "get_signed_data"
            ) as mock_get_signed_data, patch.object(
                mql_views, "MQLSelectForm"
            ) as mock_form_class, patch.object(
                mql_views, "render_to_string"
            ) as mock_render_to_string:
                # Setup mocks
                mock_get_signed_data.return_value = {"test": "data"}
                mock_form = Mock()
                mock_form.is_valid.return_value = True
                mock_form.cleaned_data = {
                    "query": {
                        "mql": "db.test.find({})",
                        "duration": 1.5,
                        "alias": "default",
                        "mql_collection": "test",
                        "mql_operation": "find",
                        "mql_args_json": json_util.dumps([{}]),
                    }
                }
                mock_form.select.return_value = ([["result"]], ["header"])
                mock_form_class.return_value = mock_form
                mock_render_to_string.return_value = "<html>content</html>"

                mock_request = Mock()
                response = mql_views.mql_select(mock_request)

                assert response.status_code == 200
                assert mock_form.select.called
                assert mock_render_to_string.called

    def test_invalid_form(self):
        """Test that invalid form returns bad request."""
        with patch("debug_toolbar.decorators.require_show_toolbar", lambda f: f):
            import importlib
            from django_mongodb_extensions.debug_toolbar.panels.mql import (
                views as mql_views,
            )

            importlib.reload(mql_views)

            with patch.object(
                mql_views, "get_signed_data"
            ) as mock_get_signed_data, patch.object(
                mql_views, "MQLSelectForm"
            ) as mock_form_class:
                mock_get_signed_data.return_value = {"test": "data"}
                mock_form = Mock()
                mock_form.is_valid.return_value = False
                mock_form_class.return_value = mock_form

                mock_request = Mock()
                response = mql_views.mql_select(mock_request)

                assert response.status_code == 400
                assert b"Form errors" in response.content

"""Tests for MQL panel."""

from unittest.mock import Mock, patch


from django_mongodb_extensions.debug_toolbar.panels.mql.panel import MQLPanel


class TestMQLPanel:
    """Test MQLPanel functionality."""

    def test_panel_initialization(self):
        """Test panel initializes with correct defaults."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        assert panel._mql_time == 0
        assert panel._queries == []
        assert panel._databases == {}
        assert panel.panel_id == "MQLPanel"

    def test_record_query(self):
        """Test recording a query."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        assert len(panel._queries) == 1
        assert panel._mql_time == 10.5
        assert "default" in panel._databases
        assert panel._databases["default"]["num_queries"] == 1
        assert panel._databases["default"]["time_spent"] == 10.5

    def test_record_multiple_queries(self):
        """Test recording multiple queries."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.record(
            alias="default",
            mql="db.posts.find({})",
            duration=5.2,
            stacktrace=[],
            mql_collection="posts",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        assert len(panel._queries) == 2
        assert panel._mql_time == 15.7
        assert panel._databases["default"]["num_queries"] == 2
        assert panel._databases["default"]["time_spent"] == 15.7

    def test_nav_subtitle(self):
        """Test nav subtitle formatting."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        # Generate stats first
        panel.generate_stats(Mock(), Mock())

        subtitle = panel.nav_subtitle
        assert "1 query" in subtitle
        assert "10.50ms" in subtitle

    def test_enable_instrumentation(self):
        """Test enabling instrumentation."""
        mock_connection = Mock()
        mock_connection._djdt_logger = None

        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.panel.connections"
        ) as mock_connections:
            mock_connections.all.return_value = [mock_connection]

            mock_toolbar = Mock()
            mock_toolbar.request = Mock()
            mock_get_response = Mock()
            panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)
            panel.enable_instrumentation()

            assert mock_connection._djdt_logger == panel

    def test_disable_instrumentation(self):
        """Test disabling instrumentation."""
        mock_connection = Mock()
        mock_connection._djdt_logger = Mock()

        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.panel.connections"
        ) as mock_connections:
            mock_connections.all.return_value = [mock_connection]

            mock_toolbar = Mock()
            mock_toolbar.request = Mock()
            mock_get_response = Mock()
            panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)
            panel.disable_instrumentation()

            assert mock_connection._djdt_logger is None

    def test_has_content(self):
        """Test has_content property."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        # No queries initially
        assert panel.has_content is False

        # Add a query
        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        assert panel.has_content is True

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.panel.dt_settings")
    def test_generate_stats_marks_slow_queries(self, mock_settings):
        """Test that slow queries are marked correctly."""
        mock_settings.get_config.return_value = {"SQL_WARNING_THRESHOLD": 10.0}

        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        # Add a slow query
        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=15.0,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        # Add a fast query
        panel.record(
            alias="default",
            mql="db.posts.find({})",
            duration=5.0,
            stacktrace=[],
            mql_collection="posts",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.generate_stats(Mock(), Mock())
        stats = panel.get_stats()

        assert stats["queries"][0]["is_slow"] is True
        assert stats["queries"][1]["is_slow"] is False

    def test_generate_stats_marks_read_operations(self):
        """Test that read operations are marked correctly."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.0,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.generate_stats(Mock(), Mock())
        stats = panel.get_stats()

        assert stats["queries"][0]["is_select"] is True

    def test_get_urls(self):
        """Test get_urls returns correct URL patterns."""
        urls = MQLPanel.get_urls()

        assert len(urls) == 2
        assert urls[0].name == "mql_select"
        assert urls[1].name == "mql_explain"

    def test_title_single_connection(self):
        """Test title with single database connection."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.generate_stats(Mock(), Mock())
        title = panel.title

        assert "1 connection" in title

    def test_title_multiple_connections(self):
        """Test title with multiple database connections."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.record(
            alias="secondary",
            mql="db.posts.find({})",
            duration=5.0,
            stacktrace=[],
            mql_collection="posts",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.generate_stats(Mock(), Mock())
        title = panel.title

        assert "2 connections" in title

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.panel.dt_settings")
    def test_generate_stats_exception_handling(self, mock_settings):
        """Test that exceptions in query grouping are handled gracefully."""
        mock_settings.get_config.return_value = {"SQL_WARNING_THRESHOLD": 10.0}

        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        # Add a query that might cause issues in grouping
        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        # Mock query_key_similar to raise an exception
        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.panel.query_key_similar",
            side_effect=Exception("Test exception"),
        ):
            # Should not raise, exception should be caught
            panel.generate_stats(Mock(), Mock())
            stats = panel.get_stats()
            assert len(stats["queries"]) == 1

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.panel.dt_settings")
    def test_generate_stats_duplicate_exception_handling(self, mock_settings):
        """Test that exceptions in duplicate query grouping are handled gracefully."""
        mock_settings.get_config.return_value = {"SQL_WARNING_THRESHOLD": 10.0}

        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        # Mock query_key_duplicate to raise an exception
        with patch(
            "django_mongodb_extensions.debug_toolbar.panels.mql.panel.query_key_duplicate",
            side_effect=Exception("Test exception"),
        ):
            # Should not raise, exception should be caught
            panel.generate_stats(Mock(), Mock())
            stats = panel.get_stats()
            assert len(stats["queries"]) == 1

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.panel.dt_settings")
    def test_generate_stats_zero_division_handling(self, mock_settings):
        """Test that zero division in width_ratio calculation is handled."""
        mock_settings.get_config.return_value = {"SQL_WARNING_THRESHOLD": 10.0}

        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        # Add a query with 0 duration
        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=0,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.generate_stats(Mock(), Mock())
        stats = panel.get_stats()

        # width_ratio should be 0 when there's a ZeroDivisionError
        assert stats["queries"][0]["width_ratio"] == 0

    def test_generate_server_timing(self):
        """Test generate_server_timing records timing correctly."""
        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=[],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.generate_stats(Mock(), Mock())

        # Mock the record_server_timing method
        panel.record_server_timing = Mock()
        panel.generate_server_timing(Mock(), Mock())

        # Verify record_server_timing was called
        panel.record_server_timing.assert_called_once()

    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.panel.render_to_string")
    @patch("django_mongodb_extensions.debug_toolbar.panels.mql.panel.render_stacktrace")
    def test_content_property(self, mock_render_stacktrace, mock_render_to_string):
        """Test content property renders template with correct data."""
        mock_render_stacktrace.return_value = "rendered stacktrace"
        mock_render_to_string.return_value = "rendered content"

        mock_toolbar = Mock()
        mock_toolbar.request = Mock()
        mock_toolbar.request_id = "test-request-id"
        mock_toolbar.stats = {}
        mock_get_response = Mock()
        panel = MQLPanel(toolbar=mock_toolbar, get_response=mock_get_response)

        panel.record(
            alias="default",
            mql="db.users.find({})",
            duration=10.5,
            stacktrace=["frame1", "frame2"],
            mql_collection="users",
            mql_operation="find",
            mql_args_json="[{}]",
        )

        panel.generate_stats(Mock(), Mock())
        content = panel.content

        # Verify render_to_string was called
        assert content == "rendered content"
        mock_render_to_string.assert_called_once()
        mock_render_stacktrace.assert_called_once()

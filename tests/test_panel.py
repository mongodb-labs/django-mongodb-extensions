"""Tests for MQL Panel.

Equivalent tests for MQL Panel based on django-debug-toolbar's SQL panel tests.
See: django-debug-toolbar/tests/panels/test_sql.py
"""

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from debug_toolbar.toolbar import DebugToolbar

from django_mongodb_extensions.debug_toolbar.panels.mql.panel import MQLPanel


rf = RequestFactory()


def mql_call():
    """Execute a MongoDB query for testing."""
    return list(User.objects.all())


class BaseMQLTestCase(TestCase):
    """Base test case for MQL Panel tests."""

    panel_id = MQLPanel.panel_id

    def setUp(self):
        self._get_response = lambda request: HttpResponse()
        self.request = rf.get("/")
        self.toolbar = DebugToolbar(self.request, self.get_response)
        self.toolbar.stats = {}
        self.panel = self.toolbar.get_panel_by_id(self.panel_id)
        self.panel.enable_instrumentation()

    def tearDown(self):
        if self.panel:
            self.panel.disable_instrumentation()
        super().tearDown()

    def get_response(self, request):
        return self._get_response(request)


class MQLPanelTests(BaseMQLTestCase):
    """Tests for MQLPanel functionality."""

    def test_disabled(self):
        """Panel can be disabled via config."""
        config = {
            "DISABLE_PANELS": {
                "django_mongodb_extensions.debug_toolbar.panels.mql.panel.MQLPanel"
            }
        }
        self.assertIs(self.panel.enabled, True)
        with self.settings(DEBUG_TOOLBAR_CONFIG=config):
            self.assertFalse(self.panel.enabled)

    def test_recording(self):
        """MQL queries are logged with proper fields."""
        self.assertEqual(len(self.panel._queries), 0)

        mql_call()

        self.assertEqual(len(self.panel._queries), 1)
        query = self.panel._queries[0]
        self.assertEqual(query["alias"], "default")
        self.assertIn("mql", query)
        self.assertIn("duration", query)
        self.assertIn("stacktrace", query)

        self.assertIs(len(query["stacktrace"]) > 0, True)

    def test_generate_server_timing(self):
        """Server timing stats generation."""
        self.assertEqual(len(self.panel._queries), 0)

        mql_call()

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.panel.generate_server_timing(self.request, response)

        self.assertEqual(len(self.panel._queries), 1)
        query = self.panel._queries[0]

        expected_data = {
            "mql_time": {"title": "MQL 1 queries", "value": query["duration"]}
        }

        self.assertEqual(self.panel.get_server_timing_stats(), expected_data)

    def test_non_ascii_query(self):
        """Non-ASCII queries are handled properly."""
        self.assertEqual(len(self.panel._queries), 0)

        list(User.objects.filter(username="thé"))
        self.assertEqual(len(self.panel._queries), 1)

        list(User.objects.filter(username="café"))
        self.assertEqual(len(self.panel._queries), 2)

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        self.assertIn("café", self.panel.content)

    def test_insert_content(self):
        """The panel only inserts content after generate_stats."""
        list(User.objects.filter(username="café"))
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        content = self.panel.content
        self.assertIn("café", content)

    @override_settings(DEBUG_TOOLBAR_CONFIG={"ENABLE_STACKTRACES": False})
    def test_disable_stacktraces(self):
        """Stacktraces can be disabled."""
        self.assertEqual(len(self.panel._queries), 0)

        mql_call()

        self.assertEqual(len(self.panel._queries), 1)
        query = self.panel._queries[0]
        self.assertEqual(query["alias"], "default")
        self.assertIn("mql", query)
        self.assertIn("duration", query)
        self.assertIn("stacktrace", query)

        self.assertEqual(query["stacktrace"], [])

    def test_similar_and_duplicate_grouping(self):
        """Grouping of similar and duplicate queries.

        In MQL, similar queries are grouped by collection and operation
        (e.g., "db.auth_user.aggregate()"), not by the specific query parameters.
        This differs from SQL where the query pattern matters.
        """
        self.assertEqual(len(self.panel._queries), 0)

        # Create queries that should be grouped
        # Use username filter since MongoDB uses ObjectId for id
        User.objects.filter(username="user1").count()  # Query A
        User.objects.filter(username="user1").count()  # Duplicate of Query A
        User.objects.filter(username="user2").count()  # Similar to A (different params)

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        self.assertEqual(len(self.panel._queries), 3)

        queries = self.panel._queries

        # First two queries are duplicates (identical MQL string)
        query = queries[0]
        self.assertIn("similar_count", query)
        self.assertEqual(query["duplicate_count"], 2)

        query = queries[1]
        self.assertIn("similar_count", query)
        self.assertEqual(query["duplicate_count"], 2)

        # Third query is similar (same operation) but not duplicate (different params)
        query = queries[2]
        self.assertIn("similar_count", query)
        self.assertNotIn("duplicate_count", query)

        # All three should have the same similar_count
        self.assertEqual(queries[0]["similar_count"], queries[1]["similar_count"])
        self.assertEqual(queries[0]["similar_count"], queries[2]["similar_count"])

        # Duplicate queries should share the same duplicate_color
        self.assertEqual(queries[0]["duplicate_color"], queries[1]["duplicate_color"])

    def test_has_content(self):
        """has_content property."""
        self.assertFalse(self.panel.has_content)

        mql_call()

        self.assertIs(self.panel.has_content, True)

    def test_nav_subtitle(self):
        """nav_subtitle displays query count and time."""
        mql_call()

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        subtitle = self.panel.nav_subtitle
        self.assertIn("1 query", subtitle)
        self.assertIn("ms", subtitle)

    def test_title(self):
        """Title displays connection count."""
        mql_call()

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        title = self.panel.title
        self.assertIn("MQL queries from", title)
        self.assertIn("connection", title)

    def test_slow_query_marking(self):
        """Slow queries are marked."""
        mql_call()

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        query = self.panel._queries[0]
        # Query should not be marked as slow (threshold is 500ms by default)
        self.assertIn("is_slow", query)
        self.assertFalse(query["is_slow"])

    @override_settings(DJDT_MQL_WARNING_THRESHOLD=0)
    def test_slow_query_marking_custom_threshold(self):
        """Slow queries are marked with custom threshold."""
        mql_call()

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        query = self.panel._queries[0]
        # With threshold of 0, all queries should be marked as slow
        self.assertIs(query["is_slow"], True)

    def test_database_tracking(self):
        """Database stats are tracked."""
        mql_call()
        mql_call()

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        self.assertEqual(len(self.panel._queries), 2)

        # Check that database stats are tracked
        self.assertIn("default", self.panel._databases)
        db_stats = self.panel._databases["default"]
        self.assertEqual(db_stats["num_queries"], 2)
        self.assertIn("time_spent", db_stats)

    def test_query_width_ratio(self):
        """Query width ratios are calculated."""
        mql_call()
        mql_call()

        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)

        for query in self.panel._queries:
            self.assertIn("width_ratio", query)
            self.assertIn("start_offset", query)
            self.assertIn("end_offset", query)

        # Width ratios should sum to approximately 100
        total_width = sum(q["width_ratio"] for q in self.panel._queries)
        self.assertAlmostEqual(total_width, 100, places=5)


class ConvertDocumentsToTableTests(TestCase):
    def setUp(self):
        from django_mongodb_extensions.debug_toolbar.panels.mql.forms import (
            MQLSelectForm,
        )

        self.form = MQLSelectForm()

    def test_empty_documents(self):
        """Empty document list returns empty rows and headers."""
        rows, headers = self.form.convert_documents_to_table([])
        self.assertEqual(rows, [])
        self.assertEqual(headers, [])

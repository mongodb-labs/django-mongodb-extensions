from debug_toolbar.toolbar import DebugToolbar
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from django_mongodb_extensions.debug_toolbar.panels.mql.panel import MQLPanel

rf = RequestFactory()


def mql_call():
    """Execute a MongoDB query for testing."""
    return list(User.objects.all())


class BaseMQLTestCase(TestCase):
    panel_id = MQLPanel.panel_id

    def setUp(self):
        self._get_response = lambda request: HttpResponse()
        self.request = rf.get("/")
        self.toolbar = DebugToolbar(self.request, self.get_response)
        self.toolbar.stats = {}
        self.panel = self.toolbar.get_panel_by_id(self.panel_id)
        self.panel.enable_instrumentation()

    def tearDown(self):
        self.panel.disable_instrumentation()

    def get_response(self, request):
        return self._get_response(request)


class MQLPanelTests(BaseMQLTestCase):
    def test_disabled(self):
        config = {
            "DISABLE_PANELS": {
                "django_mongodb_extensions.debug_toolbar.panels.mql.panel.MQLPanel"
            }
        }
        self.assertIs(self.panel.enabled, True)
        with self.settings(DEBUG_TOOLBAR_CONFIG=config):
            self.assertIs(self.panel.enabled, False)

    def test_recording(self):
        self.assertEqual(len(self.panel._queries), 0)
        mql_call()
        self.assertEqual(len(self.panel._queries), 1)
        query = self.panel._queries[0]
        self.assertEqual(query["alias"], "default")
        self.assertEqual(query["mql"], "db.auth_user.aggregate([])")
        self.assertIsInstance(query["duration"], (int, float))
        self.assertGreaterEqual(query["duration"], 0)
        self.assertIsInstance(query["stacktrace"], list)
        self.assertGreater(len(query["stacktrace"]), 0)

    def test_generate_server_timing(self):
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
        list(User.objects.filter(username="thé"))
        list(User.objects.filter(username="café"))
        self.assertEqual(len(self.panel._queries), 2)
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertIn("café", self.panel.content)

    @override_settings(DEBUG_TOOLBAR_CONFIG={"ENABLE_STACKTRACES": False})
    def test_disable_stacktraces(self):
        mql_call()
        self.assertEqual(self.panel._queries[0]["stacktrace"], [])

    def test_duplicate_grouping(self):
        """Identical queries are marked with duplicate_count and a shared color."""
        User.objects.filter(username="user1").count()
        User.objects.filter(username="user1").count()
        User.objects.filter(username="user2").count()
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertEqual(len(self.panel._queries), 3)
        queries = self.panel._queries
        # First two queries are duplicates (identical MQL string).
        self.assertEqual(queries[0]["duplicate_count"], 2)
        self.assertEqual(queries[1]["duplicate_count"], 2)
        self.assertEqual(queries[0]["duplicate_color"], queries[1]["duplicate_color"])
        # Third query has different params so is not a duplicate.
        self.assertNotIn("duplicate_count", queries[2])

    def test_has_content_property(self):
        self.assertIs(self.panel.has_content, False)
        mql_call()
        self.assertIs(self.panel.has_content, True)

    def test_nav_subtitle(self):
        mql_call()
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertRegex(self.panel.nav_subtitle, r"1 query in \d+\.\d+ms")

    def test_title(self):
        mql_call()
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertEqual(self.panel.title, "MQL queries from 1 connection")

    def test_slow_query_marking(self):
        mql_call()
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertIs(self.panel._queries[0]["is_slow"], False)

    @override_settings(DJDT_MQL_WARNING_THRESHOLD=0)
    def test_slow_query_marking_custom_threshold(self):
        mql_call()
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertIs(self.panel._queries[0]["is_slow"], True)

    def test_database_tracking(self):
        mql_call()
        mql_call()
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        self.assertEqual(len(self.panel._queries), 2)
        self.assertIn("default", self.panel._databases)
        db_stats = self.panel._databases["default"]
        self.assertEqual(db_stats["num_queries"], 2)
        self.assertGreater(db_stats["time_spent"], 0)

    def test_query_width_ratio(self):
        mql_call()
        mql_call()
        response = self.panel.process_request(self.request)
        self.panel.generate_stats(self.request, response)
        total_width = sum(q["width_ratio"] for q in self.panel._queries)
        self.assertAlmostEqual(total_width, 100, places=5)

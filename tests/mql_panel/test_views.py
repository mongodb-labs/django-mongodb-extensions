from debug_toolbar.forms import SignedDataForm
from debug_toolbar.toolbar import DebugToolbar
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from django_mongodb_extensions.mql_panel import MQLPanel

request_factory = RequestFactory()


class MQLQueryViewTests(SimpleTestCase):
    def test_invalid_signature(self):
        url = reverse("djdt:mql_query")
        response = self.client.post(url, {"signed": "invalid"})
        self.assertContains(response, "Invalid signature", status_code=400)


class MQLExplainViewTests(SimpleTestCase):
    def test_invalid_signature(self):
        url = reverse("djdt:mql_explain")
        response = self.client.post(url, {"signed": "invalid"})
        self.assertContains(response, "Invalid signature", status_code=400)


class MQLViewDataMixin:
    def setUp(self):
        request = request_factory.get("/")
        self.toolbar = DebugToolbar(request, lambda r: HttpResponse())
        self.toolbar.stats = {}
        self.panel = self.toolbar.get_panel_by_id(MQLPanel.panel_id)
        self.panel.enable_instrumentation()
        list(User.objects.all())
        response = self.panel.process_request(request)
        self.panel.generate_stats(request, response)
        self.query = self.panel._queries[0]

    def tearDown(self):
        self.panel.disable_instrumentation()

    def _post_data(self):
        return {
            "signed": SignedDataForm.sign(
                {
                    "djdt_query_id": self.query["djdt_query_id"],
                    "request_id": self.toolbar.request_id,
                }
            )
        }


class MQLQueryViewDataTests(MQLViewDataMixin, TestCase):
    def test_renders_query_results_header(self):
        response = self.client.post(reverse("djdt:mql_query"), self._post_data())
        self.assertContains(response, "Query Results")

    def test_renders_executed_mql(self):
        response = self.client.post(reverse("djdt:mql_query"), self._post_data())
        self.assertContains(response, "Executed MQL")

    def test_renders_database_alias(self):
        response = self.client.post(reverse("djdt:mql_query"), self._post_data())
        self.assertContains(response, "default")

    def test_renders_empty_set(self):
        response = self.client.post(reverse("djdt:mql_query"), self._post_data())
        self.assertContains(response, "Empty set")


class MQLExplainViewDataTests(MQLViewDataMixin, TestCase):
    def test_renders_mql_explained_header(self):
        response = self.client.post(reverse("djdt:mql_explain"), self._post_data())
        self.assertContains(response, "Explain Results")

    def test_renders_executed_mql(self):
        response = self.client.post(reverse("djdt:mql_explain"), self._post_data())
        self.assertContains(response, "Executed MQL")

    def test_renders_explain_output(self):
        response = self.client.post(reverse("djdt:mql_explain"), self._post_data())
        self.assertContains(response, "Explain Results")

from django.test import TestCase

from django_mongodb_extensions.debug_toolbar.panels.mql.utils import parse_query_args


class ParseQueryArgsTests(TestCase):
    def test_unserializable_args(self):
        """None mql_args_json raises ValueError to prevent replaying a different query."""
        with self.assertRaisesMessage(ValueError, "could not be serialized"):
            parse_query_args(
                {
                    "mql_collection": "auth_user",
                    "mql_operation": "aggregate",
                    "mql_args_json": None,
                }
            )

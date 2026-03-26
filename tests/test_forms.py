from django.test import TestCase

from django_mongodb_extensions.debug_toolbar.panels.mql.forms import MQLQueryForm


class ConvertDocumentsToTableTests(TestCase):
    def setUp(self):
        self.form = MQLQueryForm()

    def test_empty_documents(self):
        """Empty document list returns empty rows and headers."""
        rows, headers = self.form.convert_documents_to_table([])
        self.assertEqual(rows, [])
        self.assertEqual(headers, [])

    def test_handle_operation_error_format(self):
        """Error return format matches convert_documents_to_table format."""
        error = ValueError("Test error")
        mql_string = "db.test.aggregate([])"
        rows, headers = self.form._handle_operation_error(
            error, mql_string, "aggregate"
        )

        # Should return one row with one cell
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 1)

        # Cell should be a dict with 'value' and 'is_json' keys
        cell = rows[0][0]
        self.assertIsInstance(cell["value"], str)
        self.assertIs(cell["is_json"], False)

        # Should have one header
        self.assertEqual(headers[0], "Query Parsing Error")

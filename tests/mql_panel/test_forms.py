import datetime
import json

from bson import ObjectId, json_util
from django.test import TestCase

from django_mongodb_extensions.mql_panel.forms import MQLQueryForm


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


class FormatCellValueTests(TestCase):
    def setUp(self):
        self.form = MQLQueryForm()

    def test_simple_fields(self):
        """Primitive field values like in model query output."""
        cases = [
            ("username", {"value": "username", "is_json": False}),
            (42, {"value": "42", "is_json": False}),
            (3.14, {"value": "3.14", "is_json": False}),
            (True, {"value": "True", "is_json": False}),
        ]
        for input_value, expected in cases:
            with self.subTest(value=input_value):
                self.assertEqual(self.form._format_cell_value(input_value), expected)

    def test_objectid(self):
        """MongoDB ObjectId from a document."""
        oid = ObjectId()
        result = self.form._format_cell_value(oid)
        # ObjectIds serialize to {"$oid": "<id>"} which is single-key
        self.assertIs(result["is_json"], False)
        self.assertEqual(result["value"], str(json.loads(json_util.dumps(oid))["$oid"]))

    def test_datetime(self):
        """Datetime values as they might appear in a MongoDB doc."""
        dt = datetime.datetime(2024, 1, 1, 12, 30)
        result = self.form._format_cell_value(dt)
        # Datetimes serialize to {"$date": timestamp_ms} which is single-key dict
        self.assertIs(result["is_json"], False)
        self.assertEqual(result["value"], str(json.loads(json_util.dumps(dt))["$date"]))

    def test_embedded_document(self):
        """Nested dict with multiple keys (JSON formatting)."""
        embedded_doc = {
            "name": "Alice",
            "age": 30,
            "created": datetime.datetime(2024, 2, 1, 18, 0),
        }
        result = self.form._format_cell_value(embedded_doc)
        self.assertIs(result["is_json"], False)
        parsed_back = json.loads(result["value"])
        # Datetime will still be JSON date dict
        self.assertEqual(parsed_back["name"], "Alice")
        self.assertEqual(parsed_back["age"], 30)
        self.assertIn("$date", parsed_back["created"])

    def test_list_field(self):
        """A list of values as might appear in MongoDB array field."""
        arr = ["tag1", "tag2", ObjectId()]
        result = self.form._format_cell_value(arr)
        # Lists are not dicts, so is_json = False
        self.assertIs(result["is_json"], False)
        self.assertEqual(
            result["value"], '["tag1", "tag2", {"$oid": "69cc8219f859271f0a081538"}]'
        )

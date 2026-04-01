import datetime
import json

from bson import ObjectId, json_util
from django.test import TestCase

from django_mongodb_extensions.mql_panel.forms import MQLQueryForm


class MQLPanelFormTests(TestCase):
    def setUp(self):
        self.form = MQLQueryForm()

    def test_empty_documents(self):
        """Empty document list returns empty rows and headers."""
        rows, headers = self.form.convert_documents_to_table([])
        self.assertEqual(rows, [])
        self.assertEqual(headers, [])

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
        oid = "69cd52da72ad0703d3dfef51"
        result = self.form._format_cell_value(oid)
        # ObjectIds serialize to {"$oid": "<id>"} which is single-key
        self.assertIs(result["is_json"], False)
        self.assertEqual(result["value"], oid)

    def test_datetime(self):
        """Datetime values as they might appear in a MongoDB doc."""
        dt = datetime.datetime(2024, 1, 1, 12, 30)
        result = self.form._format_cell_value(dt)
        # Datetimes serialize to {"$date": timestamp_ms} which is single-key dict
        self.assertIs(result["is_json"], False)
        self.assertEqual(result["value"], str(json.loads(json_util.dumps(dt))["$date"]))

    def test_embedded_document(self):
        embedded_doc = {
            "name": "Alice",
            "age": 30,
            "created": datetime.datetime(2024, 2, 1, 18, 0),
        }
        result = self.form._format_cell_value(embedded_doc)
        self.assertEqual(result["type"], "dict")
        self.assertIs(result["is_json"], False)
        value_map = {item["key"]: item["value"] for item in result["value"]}
        self.assertEqual(value_map["name"], "Alice")
        self.assertEqual(value_map["age"], "30")
        self.assertEqual(value_map["created"], "2024-02-01T18:00:00Z")
        for item in result["value"]:
            self.assertIs(item["is_json"], False)

    def test_list_field(self):
        arr = ["tag1", "tag2", ObjectId("69cd51ddf1a98c14c906c51e")]
        result = self.form._format_cell_value(arr)
        self.assertEqual(result["type"], "list")
        self.assertIs(result["is_json"], False)
        value_map = {item["key"]: item["value"] for item in result["value"]}
        self.assertEqual(value_map[0], "tag1")
        self.assertEqual(value_map[1], "tag2")
        self.assertEqual(value_map[2], "69cd51ddf1a98c14c906c51e")  # ObjectId string
        for item in result["value"]:
            self.assertIs(item["is_json"], False)

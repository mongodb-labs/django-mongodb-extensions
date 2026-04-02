import datetime

from bson import ObjectId
from django.test import TestCase

from django_mongodb_extensions.mql_panel.forms import MQLQueryForm


class MQLPanelFormTests(TestCase):
    def setUp(self):
        self.form = MQLQueryForm()

    def test_empty_documents(self):
        rows, headers = self.form.convert_documents_to_table([])
        self.assertEqual(rows, [])
        self.assertEqual(headers, [])

    def test_simple_fields(self):
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
        oid = ObjectId("69cd52da72ad0703d3dfef51")
        result = self.form._format_cell_value(oid)
        self.assertIs(result["is_json"], False)
        self.assertEqual(result["value"], "69cd52da72ad0703d3dfef51")

    def test_datetime(self):
        dt = datetime.datetime(2024, 1, 1, 12, 30)
        result = self.form._format_cell_value(dt)
        self.assertIs(result["is_json"], False)
        self.assertEqual(result["value"], "2024-01-01T12:30:00Z")

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
        self.assertEqual(value_map[2], "69cd51ddf1a98c14c906c51e")
        for item in result["value"]:
            self.assertIs(item["is_json"], False)

    def test_list_of_embedded_dicts(self):
        tags = [
            {"name": "cool_tag", "number": 42},
            {"name": "other_tag", "number": 7},
        ]
        result = self.form._format_cell_value(tags)
        self.assertEqual(result["type"], "list")
        self.assertIs(result["is_json"], False)
        for item in result["value"]:
            self.assertEqual(item["type"], "dict")
            self.assertIs(item["is_json"], False)
            inner_map = {inner["key"]: inner["value"] for inner in item["value"]}
            self.assertIn("name", inner_map)
            self.assertIn("number", inner_map)

    def test_dict_with_nested_list_of_dicts(self):
        address = {
            "street": "123 Main St",
            "tags": [
                {"name": "cool_tag", "number": 42},
            ],
        }
        result = self.form._format_cell_value(address)
        self.assertEqual(result["type"], "dict")
        self.assertIs(result["is_json"], False)
        items_by_key = {item["key"]: item for item in result["value"]}
        self.assertEqual(items_by_key["street"]["value"], "123 Main St")
        tags_item = items_by_key["tags"]
        self.assertEqual(tags_item["type"], "list")
        self.assertIs(tags_item["is_json"], False)
        first_tag = tags_item["value"][0]
        self.assertEqual(first_tag["type"], "dict")
        inner_map = {inner["key"]: inner["value"] for inner in first_tag["value"]}
        self.assertEqual(inner_map["name"], "cool_tag")
        self.assertEqual(inner_map["number"], "42")

    def test_deeply_nested_embedded_document(self):
        address = {
            "street": "123 Main St",
            "tags": [
                {
                    "name": "cool_tag",
                    "number": 42,
                    "person": {"name": "Alice"},
                }
            ],
        }
        result = self.form._format_cell_value(address)
        self.assertEqual(result["type"], "dict")
        address_by_key = {item["key"]: item for item in result["value"]}
        tags_item = address_by_key["tags"]
        self.assertEqual(tags_item["type"], "list")
        self.assertIs(tags_item["is_json"], False)
        first_tag = tags_item["value"][0]
        self.assertEqual(first_tag["type"], "dict")
        self.assertIs(first_tag["is_json"], False)
        tag_by_key = {inner["key"]: inner for inner in first_tag["value"]}
        self.assertEqual(tag_by_key["name"]["value"], "cool_tag")
        self.assertEqual(tag_by_key["number"]["value"], "42")
        person_item = tag_by_key["person"]
        self.assertEqual(person_item["type"], "dict")
        self.assertIs(person_item["is_json"], False)
        person_map = {inner["key"]: inner["value"] for inner in person_item["value"]}
        self.assertEqual(person_map["name"], "Alice")

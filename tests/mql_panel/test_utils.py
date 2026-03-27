from django.db import connection
from django.test import TestCase

from django_mongodb_extensions.mql_panel.utils import (
    QueryParts,
)


class QueryPartsTests(TestCase):
    def test_initialization(self):
        query_dict = {"mql": "db.auth_user.aggregate([])", "alias": "default"}
        db = connection.database
        collection = db["auth_user"]
        query_parts = QueryParts(
            query_dict=query_dict,
            alias="default",
            mql_string="db.auth_user.aggregate([])",
            connection=connection,
            db=db,
            collection=collection,
            collection_name="auth_user",
            operation="aggregate",
            args_list=[[]],
        )
        self.assertEqual(query_parts.query_dict, query_dict)
        self.assertEqual(query_parts.alias, "default")
        self.assertEqual(query_parts.mql_string, "db.auth_user.aggregate([])")
        self.assertEqual(query_parts.collection_name, "auth_user")
        self.assertEqual(query_parts.operation, "aggregate")
        self.assertEqual(query_parts.args_list, [[]])
        self.assertIs(query_parts.connection, connection)
        self.assertIs(query_parts.db, db)
        self.assertIs(query_parts.collection, collection)

import types

from django_mongodb_backend.utils import OperationDebugWrapper
from pymongo.collection import Collection


def patch_get_collection(connection):
    """
    Patch the get_collection method of the connection to return a wrapped
    Collection object that logs queries for the debug toolbar.
    """

    def get_collection(self, name, **kwargs):
        return DebugToolbarWrapper(
            self, Collection(self.database, name, **kwargs), connection._djdt_logger
        )

    connection.get_collection = types.MethodType(get_collection, connection)


class DebugToolbarWrapper(OperationDebugWrapper):
    """
    A wrapper around pymongo Collection objects that logs queries for the
    debug toolbar.
    """

    def __init__(self, db, collection, logger):
        super().__init__(db, collection)
        self.logger = logger

    def log(self, op, duration, args, kwargs=None):
        args = ", ".join(repr(arg) for arg in args)
        operation = f"db.{self.collection_name}{op}({args})"
        if self.logger:
            self.logger._sql_time += duration
            self.logger._queries.append(
                {
                    "alias": self.db.alias,
                    "sql": operation,
                    "duration": "%.3f" % duration,
                }
            )
            self.logger._databases[self.db.alias] = {
                "num_queries": len(self.logger._queries),
            }

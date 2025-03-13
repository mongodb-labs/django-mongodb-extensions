import types

from django.conf import settings
from django.db.backends.utils import logger
from django_mongodb_backend.utils import OperationDebugWrapper
from pymongo.collection import Collection


def patch_get_collection(connection):
    def get_collection(self, name, **kwargs):
        collection = Collection(self.database, name, **kwargs)
        collection = DebugToolbarWrapper(self, collection)
        return collection

    connection.get_collection = types.MethodType(get_collection, connection)


def patch_wrapper_with_mixin(base_wrapper, mixin):
    class DjDTCursorWrapper(mixin, base_wrapper):
        pass

    return DjDTCursorWrapper


class DjDTCursorWrapperMixin:
    def __init__(self, cursor, db, logger):
        super().__init__(cursor, db)
        self.logger = logger


class DebugToolbarWrapper(OperationDebugWrapper):
    def log(self, op, duration, args, kwargs=None):
        msg = "(%.3f) %s"
        args = ", ".join(repr(arg) for arg in args)
        operation = f"db.{self.collection_name}{op}({args})"
        if len(settings.DATABASES) > 1:
            msg += f"; alias={self.db.alias}"
        self.db.queries_log.append(
            {
                "sql": operation,
                "time": "%.3f" % duration,
            }
        )
        logger.info(
            msg,
            duration,
            operation,
            extra={
                "duration": duration,
                "sql": operation,
                "alias": self.db.alias,
            },
        )

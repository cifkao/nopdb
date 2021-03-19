import abc
import threading
from types import FrameType
from typing import Any, Callable, List, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from .nopdb import NoPdb
    from .scope import Scope


TraceFunc = Callable[[FrameType, str, Any], Any]


THREAD_LOCAL = threading.local()


class Handle:
    pass


# Some functions for suspending and resuming tracing internally. We cannot have
# a @contextlib.contextmanager for this, because the __enter__ would end up being
# traced. So we just define two functions and use them with try-finally.
# Note that these are only necessary to use in code that uses other libraries.


def suspend():
    THREAD_LOCAL.suspended = getattr(THREAD_LOCAL, "suspended", 0) + 1


def resume():
    THREAD_LOCAL.suspended -= 1


def is_suspended():
    return getattr(THREAD_LOCAL, "suspended", 0) > 0


TNoPdbContextManager = TypeVar("TNoPdbContextManager", bound="NoPdbContextManager")


class NoPdbContextManager(abc.ABC):
    def __init__(self, nopdb: "NoPdb", scope: "Scope", events: List[str]):
        self._nopdb = nopdb
        self._scope = scope
        self._events = events

        self._was_started = False
        self._handle = nopdb.add_callback(self._scope, self._callback, self._events)

    @abc.abstractmethod
    def _callback(self, frame: FrameType, event: str, arg: Any) -> None:
        pass

    def __enter__(self: TNoPdbContextManager) -> TNoPdbContextManager:
        self._was_started = self._nopdb.started
        self._nopdb._ensure_started()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            self._nopdb.remove_callback(self._handle)
        finally:
            if self._nopdb.started and not self._was_started:
                self._nopdb.stop()
